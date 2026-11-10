"""Triagem de exógenas usando exclusivamente o recorte de desenvolvimento."""
import warnings

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests
from statsmodels.tools.sm_exceptions import InfeasibleTestError
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import grangercausalitytests

from modelos import MINIMOS
from referencia import CORTE_DEV


def _correlacao(a, b, metodo):
    par = pd.concat([a, b], axis=1).dropna()
    if len(par) < 30 or min(par.nunique()) < 2:
        return np.nan
    return par.iloc[:, 0].corr(par.iloc[:, 1], method=metodo)


def diagnosticar(dados, saida):
    d = dados.loc[dados.mes.le(CORTE_DEV)].copy()
    colunas = [nome for nome in MINIMOS if nome in d]
    linhas = []
    granger = []
    for aid, acude in d.groupby("acude_id"):
        y = acude.volume_pct
        dy = y.diff()
        for nome in colunas:
            x = acude[nome]
            dx = x.diff()
            for lag in range(13):
                linhas.append({"acude_id": aid, "variavel": nome, "lag": lag,
                               "pearson_nivel": _correlacao(y, x.shift(lag), "pearson"),
                               "spearman_nivel": _correlacao(y, x.shift(lag), "spearman"),
                               "pearson_diferenca": _correlacao(dy, dx.shift(lag), "pearson"),
                               "spearman_diferenca": _correlacao(dy, dx.shift(lag), "spearman")})
            matriz = pd.DataFrame({"delta_volume": dy, "delta_x": dx})
            lacuna = matriz.isna().any(axis=1)
            blocos = [b.dropna() for _, b in matriz.groupby(lacuna.cumsum())]
            bloco = max(blocos, key=len)
            if len(bloco) < 42 or min(bloco.nunique()) < 2:
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", FutureWarning)
                    testes = grangercausalitytests(bloco, maxlag=6)
                for lag, teste in testes.items():
                    granger.append({"acude_id": aid, "variavel": nome, "lag": lag,
                                    "n": len(bloco), "p": teste[0]["ssr_ftest"][1]})
            except (ValueError, np.linalg.LinAlgError, InfeasibleTestError):
                continue
    correlacoes = pd.DataFrame(linhas)
    g = pd.DataFrame(granger)
    g["p_fdr_bh"] = multipletests(g.p, method="fdr_bh")[1]
    candidatos = correlacoes.loc[correlacoes.lag.between(1, 6)].copy()
    candidatos["abs_r"] = candidatos.spearman_diferenca.abs()
    resumo = candidatos.groupby(["variavel", "lag"]).abs_r.agg(["median", "count"]).reset_index()
    escolhidos = (resumo.sort_values(["median", "lag"], ascending=[False, True])
                  .drop_duplicates("variavel").set_index("variavel"))
    lags = escolhidos.lag.astype(int).to_dict()

    design = pd.DataFrame({nome: d.groupby("acude_id")[nome].shift(lag)
                           for nome, lag in lags.items()}).dropna()
    vif = []
    ativos = list(lags)
    while ativos:
        matriz = design[ativos]
        if len(matriz) < 30:
            break
        z = (matriz - matriz.mean()) / matriz.std()
        if len(ativos) == 1:
            valores = {ativos[0]: 1.0}
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                valores = {v: variance_inflation_factor(z.to_numpy(), i) for i, v in enumerate(ativos)}
        pior = max(valores, key=valores.get)
        remover = pior if valores[pior] > 10 else None
        vif.extend({"rodada": len(lags) - len(ativos) + 1, "variavel": v, "VIF": val,
                    "removida": v == remover} for v, val in valores.items())
        if remover is None:
            break
        ativos.remove(remover)
    final = {v: lags[v] for v in ativos}
    escolhidos["selecionada"] = escolhidos.index.isin(ativos)
    saida.mkdir(exist_ok=True)
    correlacoes.to_csv(saida / "correlacoes_lags.csv.gz", index=False)
    g.to_csv(saida / "granger.csv.gz", index=False)
    pd.DataFrame(vif).to_csv(saida / "vif.csv", index=False)
    escolhidos.to_csv(saida / "atrasos_escolhidos.csv")
    return final
