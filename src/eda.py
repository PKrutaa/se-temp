"""Diagnóstico descritivo da série de volume."""
import warnings

import pandas as pd
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import acf, adfuller, kpss


def bloco_contiguo(serie):
    blocos = serie.groupby(serie.isna().cumsum())
    return max((bloco.dropna() for _, bloco in blocos), key=len, default=serie.iloc[:0])


def descrever(base, painel):
    resumos = []
    for acude_id, serie in painel.items():
        x = bloco_contiguo(serie)
        info = {
            "acude_id": acude_id, "observacoes": int(serie.count()),
            "ausentes": int(serie.isna().sum()), "mediana_pct": serie.median(),
            "min_pct": serie.min(), "max_pct": serie.max(), "dp_pp": serie.std(),
            "meses_criticos": int(serie.lt(5).sum()), "bloco_contiguo": len(x),
        }
        if len(x) >= 36 and x.nunique() > 1:
            try:
                info["ADF_p"] = adfuller(x, result_object=False)[1]
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", InterpolationWarning)
                    info["KPSS_p_limitado"] = kpss(x, regression="c", nlags="auto", result_object=False)[1]
                info["ACF_nivel_12"] = acf(x, nlags=12)[12]
                info["ACF_diferenca_12"] = acf(x.diff().dropna(), nlags=12)[12]
            except (ValueError, OverflowError, ZeroDivisionError):
                info["diagnostico_invalido"] = True
        resumos.append(info)
    return pd.DataFrame(resumos).merge(base[["acude_id", "acude"]].drop_duplicates(), on="acude_id")


def plotar_stl(serie):
    x = bloco_contiguo(serie)
    if len(x) < 36:
        raise ValueError("STL requer pelo menos 36 meses contíguos.")
    x.index = x.index.to_timestamp()
    return STL(x, period=12, robust=True).fit().plot()


def auditar_medicoes(base):
    """Sinaliza discrepâncias sem alterar a série observada."""
    d = base.sort_values(["acude_id", "mes"]).copy()
    razao = d.volume_m3.div(d.capacidade_m3.where(d.capacidade_m3.gt(0))) * 100
    d["diferenca_capacidade_pp"] = d.volume_pct - razao
    d["dias_ate_fim_mes"] = (d.mes.dt.end_time.dt.normalize() - d.data_coleta).dt.days
    d["salto_mensal_pp"] = d.groupby("acude_id").volume_pct.diff()
    return d.assign(
        acima_capacidade=d.volume_pct.gt(100),
        diferenca_capacidade_gt_1pp=d.diferenca_capacidade_pp.abs().gt(1),
        leitura_mais_15_dias_antes=d.dias_ate_fim_mes.gt(15),
        salto_gt_40pp=d.salto_mensal_pp.abs().gt(40),
    )[["acude_id", "acude", "mes", "volume_pct", "data_coleta", "dias_ate_fim_mes",
       "diferenca_capacidade_pp", "salto_mensal_pp", "acima_capacidade",
       "diferenca_capacidade_gt_1pp", "leitura_mais_15_dias_antes", "salto_gt_40pp"]]
