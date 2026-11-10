"""Comparação temporal com alvos observados até cada origem."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

import warnings
import numpy as np
import pandas as pd
from scipy.stats import t as student
from sklearn.ensemble import HistGradientBoostingRegressor
from statsmodels.stats.multitest import multipletests
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.statespace.sarimax import SARIMAX
import torch
from torch import nn

from referencia import (CALIBRACAO, CORTE_DEV, HORIZONTES, TESTE_INICIO, calibrar,
                        comparaveis, medir, preparar_painel, prever_referencias)

SEMENTE = 621
FIM_RANK = pd.Period("2024-06", "M")
MINIMOS = {"nino34_anom_c": 1, "monitor_pb_ge_s0_pct": 1, "monitor_local_severidade": 1,
           "chuva_mm": 1, "temperatura_c": 1, "et_fluxo_mj_m2_dia": 1}


def dados_modelo(pasta):
    base, volume = preparar_painel(pasta / "acudes_mensal.csv")
    exogenas = pd.read_csv(pasta / "exogenas_pb_mensal.csv")
    exogenas["mes"] = pd.PeriodIndex(exogenas.mes, freq="M")
    exogenas["monitor_catalogo_mes"] = pd.to_datetime(
        exogenas.monitor_data_criacao, errors="coerce"
    ).dt.to_period("M")
    dados = base.merge(exogenas, on="mes", validate="m:1")
    clima_csv = pasta / "clima_bacias_mensal.csv"
    if clima_csv.exists():
        clima = pd.read_csv(clima_csv)
        clima["mes"] = pd.PeriodIndex(clima.mes, freq="M")
        dados = dados.merge(clima[["bacia_id", "mes", "chuva_mm", "temperatura_c", "et_fluxo_mj_m2_dia"]],
                            on=["bacia_id", "mes"], validate="m:1")
    monitor_csv = pasta / "monitor_local_mensal.csv"
    if monitor_csv.exists():
        local = pd.read_csv(monitor_csv)
        local["mes"] = pd.PeriodIndex(local.mes, freq="M")
        dados = dados.merge(local, on=["acude_id", "mes"], how="left", validate="1:1")
    return dados.sort_values(["acude_id", "mes"]), volume


def preparar_features(dados, lags, indice=None):
    d = dados.copy()
    por_acude = d.groupby("acude_id")
    d["log_capacidade"] = np.log10(d.capacidade_m3.where(d.capacidade_m3.gt(0)))
    for lag in (0, 1, 2, 3, 6, 12):
        d[f"vol_l{lag}"] = por_acude.volume_pct.shift(lag)
    for janela in (3, 6):
        d[f"media_{janela}"] = por_acude.volume_pct.transform(
            lambda s: s.rolling(janela, min_periods=2).mean()
        )
    d["ultimo_volume"] = por_acude.volume_pct.ffill(limit=2)
    covariaveis = []
    for variavel, lag in lags.items():
        if variavel not in d:
            continue
        coluna = f"{variavel}_l{lag}"
        d[coluna] = por_acude[variavel].shift(lag)
        if variavel.startswith("monitor_"):
            criado = por_acude.monitor_catalogo_mes.shift(lag)
            d[coluna] = d[coluna].where(criado.le(d.mes))
        covariaveis.append(coluna)
    if indice is not None:
        d = d.merge(indice, on="mes", how="left", validate="m:1")
        covariaveis.append("indice_alarme")
    estaticas = ["latitude", "longitude", "log_capacidade", *covariaveis]
    colunas = ["vol_l0", "vol_l1", "vol_l2", "vol_l3", "vol_l6", "vol_l12",
               "media_3", "media_6", "ultimo_volume", "seno", "cosseno", "horizonte", *estaticas]
    meses = d.mes.astype("int64").to_numpy()
    acudes = d.acude_id.to_numpy()
    historico = np.stack([por_acude.volume_pct.shift(i).to_numpy()
                          for i in range(11, -1, -1)], axis=1)
    return d, meses, acudes, historico, colunas


class Rede(nn.Module):
    def __init__(self, n_features):
        super().__init__()
        self.lstm = nn.LSTM(2, 10, batch_first=True)
        self.saida = nn.Sequential(nn.Linear(10 + n_features, 16), nn.ReLU(), nn.Linear(16, 4))

    def forward(self, serie, features):
        passos, _ = self.lstm(serie)
        return self.saida(torch.cat((passos[:, -1], features), dim=1))


def ajustar_lstm(serie, features, alvos, treino, teste):
    torch.manual_seed(SEMENTE)
    ajuste = features[treino]
    tem_valor = np.isfinite(ajuste).any(axis=0)
    centro = np.zeros(features.shape[1])
    escala = np.ones(features.shape[1])
    centro[tem_valor] = np.nanmean(ajuste[:, tem_valor], axis=0)
    escala[tem_valor] = np.nanstd(ajuste[:, tem_valor], axis=0).clip(0.01)
    padronizado = (features - centro) / escala
    matriz = np.concatenate([np.nan_to_num(padronizado, nan=0).clip(-12, 12),
                             np.isfinite(features)], axis=1)
    s = torch.tensor(np.stack([np.nan_to_num(serie / 100, nan=0),
                               np.isfinite(serie)], axis=-1), dtype=torch.float32)
    x = torch.tensor(matriz, dtype=torch.float32)
    y = torch.tensor(alvos / 100, dtype=torch.float32)
    r = Rede(x.shape[1])
    opt = torch.optim.Adam(r.parameters(), lr=0.004)
    indices = torch.tensor(np.flatnonzero(treino))
    # Fixed-size training sample drawn only from eligible observations at the origin.
    indices = indices[torch.randperm(len(indices))[:5000]]
    r.train()
    for _ in range(5):
        ordem = indices[torch.randperm(len(indices))]
        for lote in ordem.split(512):
            esperado = y[lote]
            validos = torch.isfinite(esperado)
            previsto = r(s[lote], x[lote])
            perda = nn.functional.smooth_l1_loss(previsto[validos], esperado[validos], beta=0.1)
            opt.zero_grad()
            perda.backward()
            opt.step()
    r.eval()
    with torch.no_grad():
        return r(s[teste], x[teste]).numpy() * 100


def ajuste_arima(volume, origens):
    previsoes = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        for aid, serie in volume.items():
            treino = serie.loc[:CORTE_DEV]
            modelo = SARIMAX(treino.to_numpy(), order=(1, 1, 0), trend="n")
            ajuste = modelo.fit(disp=False, maxiter=50)
            if not np.isfinite(ajuste.params).all():
                continue
            cursor = CORTE_DEV
            for origem in origens:
                if origem > cursor:
                    atualizacao = serie.loc[cursor + 1:origem]
                    ajuste = ajuste.extend(atualizacao.to_numpy())
                    cursor = origem
                previsoes[(origem, aid)] = np.asarray(ajuste.forecast(6))[2:]
    return previsoes


def _criar_linhas(referencias, modelo, previsoes):
    molde = referencias.loc[referencias.modelo.eq("Persistência")].copy()
    molde["modelo"] = modelo
    molde["previsto"] = [previsoes.get((aid, h), np.nan)
                         for aid, h in zip(molde.acude_id, molde.horizonte)]
    molde["previsto"] = molde.previsto.clip(lower=0)
    return molde


def gerar(dados, volume, lags, apenas=None, indice=None):
    torch.set_num_threads(1)
    coorte = volume.loc[:CORTE_DEV].count().loc[lambda s: s.ge(60)].index
    volume = volume[coorte]
    dados = dados[dados.acude_id.isin(coorte)]
    d, meses, aids, historia, colunas = preparar_features(dados, lags, indice)
    alvos = np.stack([d.groupby("acude_id").volume_pct.shift(-h).to_numpy()
                      for h in HORIZONTES], axis=1)
    origem_final = volume.index.max()
    origens = pd.period_range(CORTE_DEV, origem_final, freq="M")
    origens = [o for o in origens if o <= origem_final - 3 or o == origem_final]
    usar = {apenas} if apenas else {"SARIMAX", "Gradient boosting", "LSTM", "Sazonal", "Persistência"}
    arima = ajuste_arima(volume, origens) if "SARIMAX" in usar else {}
    tabular = {}
    for h in HORIZONTES:
        alvo_mes = d.mes + h
        matriz = d.assign(seno=np.sin(2 * np.pi * alvo_mes.dt.month / 12),
                          cosseno=np.cos(2 * np.pi * alvo_mes.dt.month / 12), horizonte=h)
        tabular[h] = matriz[colunas].to_numpy(dtype=float)
    lstm_features = d[[c for c in colunas if c not in ("seno", "cosseno", "horizonte")]].assign(
        seno=np.sin(2 * np.pi * d.mes.dt.month / 12),
        cosseno=np.cos(2 * np.pi * d.mes.dt.month / 12),
    ).to_numpy(dtype=float)
    recente = d.ultimo_volume.notna().to_numpy()
    todas = []
    for origem in origens:
        ref = prever_referencias(volume, origem)
        amostra = (meses == origem.ordinal) & recente
        if "Sazonal" in usar or "Persistência" in usar:
            todas.append(ref[ref.modelo.isin(usar)])
        if "SARIMAX" in usar:
            valores = {(aid, h): valor for aid in aids[amostra]
                       for h, valor in zip(HORIZONTES, arima.get((origem, aid), [np.nan] * 4))}
            todas.append(_criar_linhas(ref, "SARIMAX", valores))
        if "Gradient boosting" in usar:
            valores = {}
            for j, h in enumerate(HORIZONTES):
                treino = (meses + h <= origem.ordinal) & recente & np.isfinite(alvos[:, j])
                x = tabular[h]
                modelo = HistGradientBoostingRegressor(
                    max_iter=85, max_leaf_nodes=15, l2_regularization=1, learning_rate=0.09,
                    early_stopping=False, random_state=SEMENTE,
                )
                modelo.fit(x[treino], alvos[treino, j] - d.ultimo_volume.to_numpy()[treino])
                pred = modelo.predict(x[amostra]) + d.ultimo_volume.to_numpy()[amostra]
                valores.update({(aid, h): valor for aid, valor in zip(aids[amostra], pred)})
            todas.append(_criar_linhas(ref, "Gradient boosting", valores))
        if "LSTM" in usar:
            conhecidos = meses[:, None] + np.asarray(HORIZONTES) <= origem.ordinal
            y = np.where(conhecidos, alvos, np.nan)
            treino = recente & np.isfinite(y).any(axis=1)
            pred = ajustar_lstm(historia, lstm_features, y, treino, amostra)
            valores = {(aid, h): pred[i, j] for i, aid in enumerate(aids[amostra])
                       for j, h in enumerate(HORIZONTES)}
            todas.append(_criar_linhas(ref, "LSTM", valores))
        print(f"Origem {origem} concluída", flush=True)
    return pd.concat(todas, ignore_index=True)


def diebold_mariano(pares, modelos):
    resultados = []
    for h, grupo in pares[pares.modelo.isin(modelos)].groupby("horizonte"):
        erros = grupo.assign(perda=(grupo.observado - grupo.previsto).abs())
        d = erros.groupby(["origem", "modelo"]).perda.mean().unstack()
        d = (d[modelos[0]] - d[modelos[1]]).dropna().sort_index()
        n = len(d)
        teste = p = np.nan
        if n > h + 1:
            central = d.to_numpy() - d.mean()
            var = np.dot(central, central) / n
            for j in range(1, h):
                var += 2 * (1 - j / h) * np.dot(central[j:], central[:-j]) / n
            if var > 0:
                correcao = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
                teste = correcao * d.mean() / np.sqrt(var / n)
                p = 2 * student.sf(abs(teste), df=n - 1)
        resultados.append({"horizonte": h, "origens": n, "modelo_a": modelos[0],
                           "modelo_b": modelos[1], "dif_perda_pp": d.mean(), "DM_HLN": teste,
                           "p": p})
    dm = pd.DataFrame(resultados)
    validos = dm.p.notna()
    dm["p_holm"] = np.nan
    if validos.any():
        dm.loc[validos, "p_holm"] = multipletests(dm.loc[validos, "p"], method="holm")[1]
    return dm


def avaliar(previsoes, dados, saida):
    calibracao = comparaveis(previsoes.loc[previsoes.mes_alvo.between(*CALIBRACAO)])
    rank = calibracao.loc[calibracao.mes_alvo.le(FIM_RANK)].assign(
        erro=lambda x: (x.observado - x.previsto).abs()
    ).groupby(["modelo", "horizonte"]).erro.mean().groupby("modelo").mean().sort_values()
    orig_final = previsoes.origem.max()
    teste_bruto = previsoes.loc[previsoes.mes_alvo.between(TESTE_INICIO, orig_final)]
    teste = comparaveis(teste_bruto)
    teste = pd.concat([
        calibrar(calibracao.loc[calibracao.mes_alvo.le(origem)], grupo)
        for origem, grupo in teste.groupby("origem")
    ], ignore_index=True)
    metricas = pd.DataFrame([
        {"modelo": modelo, "horizonte": h, **medir(grupo),
         "MAE_macro_pp": (grupo.observado - grupo.previsto).abs().groupby(grupo.acude_id).mean().mean()}
        for (modelo, h), grupo in teste.groupby(["modelo", "horizonte"])
    ])
    cobertura = teste_bruto.assign(valida=lambda d: d.previsto.notna() & d.observado.notna()).groupby(
        ["modelo", "horizonte"]
    ).valida.agg(["sum", "size"])
    futuro = calibrar(calibracao, previsoes.loc[previsoes.origem.eq(orig_final) &
                                               previsoes.modelo.eq(rank.index[0])]).drop(
        columns=["observado", "escala"]
    )
    catalogo = dados[["acude_id", "acude", "municipio", "bacia", "latitude", "longitude"]].drop_duplicates("acude_id")
    grade = catalogo.merge(pd.DataFrame({"horizonte": HORIZONTES}), how="cross")
    futuro = grade.merge(futuro, on=["acude_id", "horizonte"], how="left", validate="1:1")
    futuro["origem"] = orig_final
    futuro["mes_alvo"] = futuro.horizonte.map(lambda h: orig_final + h)
    futuro["modelo"] = rank.index[0]
    medicao = dados.dropna(subset=["volume_pct"]).groupby("acude_id").data_coleta.max()
    futuro["ultima_leitura"] = futuro.acude_id.map(medicao)
    futuro["fora_coorte"] = ~futuro.acude_id.isin(previsoes.acude_id)
    futuro["critico_pontual"] = futuro.previsto.lt(5).where(futuro.previsto.notna()).astype("boolean")
    futuro["intervalo_cruza_5"] = (futuro.inferior_90.lt(5) & futuro.superior_90.ge(5)).where(
        futuro.inferior_90.notna() & futuro.superior_90.notna()
    ).astype("boolean")
    dm = diebold_mariano(teste, list(rank.index[:2]))
    saida.mkdir(exist_ok=True)
    metricas.to_csv(saida / "metricas_modelos.csv", index=False)
    rank.rename("MAE_validacao_pp").to_csv(saida / "ranking_validacao.csv")
    cobertura.to_csv(saida / "cobertura_modelos.csv")
    futuro.to_csv(saida / "previsoes_modelo_escolhido.csv", index=False)
    dm.to_csv(saida / "diebold_mariano.csv", index=False)
    teste.to_csv(saida / "previsoes_teste_pareadas.csv.gz", index=False)
    return metricas, rank, futuro, dm
