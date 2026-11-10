"""Compara Acauã entre AESA e ANA/SAR na mesma data de coleta."""
import io
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

ANA = "https://www.ana.gov.br/sar0/Medicao"
PARAMETROS = {
    "dropDownListEstados": "16", "dropDownListReservatorios": "12005",
    "dataInicial": "01/01/2012", "dataFinal": "31/10/2026", "button": "Buscar",
}


def comparar_acaua(painel):
    with urlopen(f"{ANA}?{urlencode(PARAMETROS)}", timeout=60) as resposta:
        html = resposta.read().decode("utf-8")
    sar, = pd.read_html(io.StringIO(html), decimal=",", thousands=".", match="Data da Medição")
    sar.columns = ["estado", "nome_sar", "capacidade_hm3_sar", "cota_m_sar",
                   "volume_hm3_sar", "volume_pct_sar", "data_coleta"]
    sar["data_coleta"] = pd.to_datetime(sar["data_coleta"], format="%d/%m/%Y")
    sar = sar.drop_duplicates().loc[lambda d: ~d["data_coleta"].duplicated(keep=False)]
    aesa = painel.loc[painel["acude_id"].eq(126) & painel["data_coleta"].notna(),
                      ["mes", "data_coleta", "capacidade_m3", "volume_m3", "volume_pct"]]
    pares = aesa.merge(sar, on="data_coleta", validate="1:1")
    pares["diferenca_pp"] = pares["volume_pct"] - pares["volume_pct_sar"]
    return pares


if __name__ == "__main__":
    painel = pd.read_csv(Path("data/acudes_mensal.csv"), parse_dates=["data_coleta"])
    pares = comparar_acaua(painel)
    pares.to_csv("data/ana_aesa_acaua.csv", index=False)
    print(f"{len(pares)} pares na mesma data.")
    print(pares["diferenca_pp"].abs().describe())
