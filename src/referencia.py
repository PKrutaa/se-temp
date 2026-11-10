"""Referências mensais, métricas e intervalo empírico por horizonte."""
import numpy as np
import pandas as pd

HORIZONTES = (3, 4, 5, 6)
CALIBRACAO = (pd.Period("2023-01", "M"), pd.Period("2024-12", "M"))
TESTE_INICIO = pd.Period("2025-01", "M")
CORTE_DEV = pd.Period("2022-12", "M")


def preparar_painel(caminho="data/acudes_mensal.csv"):
    base = pd.read_csv(caminho, parse_dates=["mes", "data_coleta"])
    base["mes"] = base["mes"].dt.to_period("M")
    painel = base.pivot(index="mes", columns="acude_id", values="volume_pct").sort_index()
    assert painel.index.equals(pd.period_range(painel.index.min(), painel.index.max(), freq="M"))
    return base, painel


def prever_referencias(painel, origem):
    """Apenas medições observadas e com mês <= origem entram na previsão."""
    treino = painel.loc[:origem]
    escala = (treino - treino.shift(12)).abs().mean().replace(0, np.nan)
    saidas = []
    for horizonte in HORIZONTES:
        alvo = origem + horizonte
        sazonal = treino.loc[alvo - 12]
        persistencia = treino.loc[origem]
        observado = painel.reindex([alvo]).iloc[0]
        for modelo, previsto in (("Sazonal", sazonal), ("Persistência", persistencia)):
            saidas.append(pd.DataFrame({
                "origem": origem, "mes_alvo": alvo, "horizonte": horizonte,
                "modelo": modelo, "previsto": previsto, "observado": observado, "escala": escala,
            }).rename_axis("acude_id").reset_index())
    return pd.concat(saidas, ignore_index=True)


def comparaveis(previsoes):
    chave = ["acude_id", "origem", "mes_alvo", "horizonte"]
    validos = previsoes.dropna(subset=["previsto", "observado"]).copy()
    pares = validos.groupby(chave)["modelo"].transform("nunique").eq(previsoes["modelo"].nunique())
    return validos.loc[pares].copy()


def calibrar(calibracao, previsoes):
    calibracao = calibracao.assign(erro=calibracao["observado"] - calibracao["previsto"])
    limites = (calibracao.groupby(["modelo", "horizonte"])["erro"]
               .quantile([0.05, 0.95]).unstack().rename(columns={0.05: "q05", 0.95: "q95"}))
    saida = previsoes.join(limites, on=["modelo", "horizonte"])
    saida["inferior_90"] = (saida["previsto"] + saida.pop("q05")).clip(lower=0)
    saida["superior_90"] = (saida["previsto"] + saida.pop("q95")).clip(lower=0)
    return saida


def medir(grupo):
    y = grupo["observado"]
    p = grupo["previsto"]
    erro = (y - p).abs()
    positivos = y.gt(0)
    critico = y.lt(5)
    alerta = p.lt(5)
    tp = int((critico & alerta).sum())
    fp = int((~critico & alerta).sum())
    fn = int((critico & ~alerta).sum())
    tn = int((~critico & ~alerta).sum())
    denominador = y.abs() + p.abs()
    smape = 200 * erro.div(denominador.where(denominador.ne(0))).fillna(0)
    intervalo = grupo.dropna(subset=["inferior_90", "superior_90"])
    cobertos = intervalo["observado"].between(intervalo["inferior_90"], intervalo["superior_90"])
    return {
        "n": len(y), "MAE_pp": erro.mean(), "RMSE_pp": np.sqrt(erro.pow(2).mean()),
        "n_MAPE": int(positivos.sum()), "MAPE_pct": 100 * erro[positivos].div(y[positivos]).mean(),
        "sMAPE_pct": smape.mean(), "MASE": erro.div(grupo["escala"]).mean(),
        "n_MASE": int(grupo["escala"].notna().sum()),
        "VP": tp, "FP": fp, "FN": fn, "VN": tn,
        "precisao": tp / (tp + fp) if tp + fp else np.nan,
        "recall": tp / (tp + fn) if tp + fn else np.nan,
        "F1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else np.nan,
        "n_intervalos": len(intervalo), "cobertura_90": cobertos.mean(),
        "largura_90_pp": (intervalo["superior_90"] - intervalo["inferior_90"]).mean(),
    }


def executar(painel):
    coorte = painel.loc[:CORTE_DEV].count().loc[lambda s: s.ge(60)].index
    painel = painel[coorte]
    ultima = painel.index.max()
    origens = pd.period_range(CALIBRACAO[0] - max(HORIZONTES), ultima - min(HORIZONTES), freq="M")
    previsoes = pd.concat([prever_referencias(painel, origem) for origem in origens], ignore_index=True)
    calibracao = comparaveis(previsoes.loc[previsoes["mes_alvo"].between(*CALIBRACAO)])
    teste = comparaveis(previsoes.loc[previsoes["mes_alvo"].between(TESTE_INICIO, ultima)])
    teste = pd.concat([
        calibrar(calibracao.loc[calibracao["mes_alvo"].le(origem)], grupo)
        for origem, grupo in teste.groupby("origem")
    ], ignore_index=True)
    metricas = pd.DataFrame([
        {"modelo": modelo, "horizonte": h, **medir(grupo)}
        for (modelo, h), grupo in teste.groupby(["modelo", "horizonte"])
    ])
    futuro = calibrar(calibracao, prever_referencias(painel, ultima))
    futuro = futuro.drop(columns=["observado", "escala"])
    futuro["critico_pontual"] = futuro["previsto"].lt(5).where(futuro["previsto"].notna()).astype("boolean")
    return coorte, metricas, futuro
