"""Obtém séries explicativas estaduais com datas de referência separadas."""
import csv
from datetime import date
import json
from pathlib import Path
from urllib.request import urlopen

NOAA = "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices"
ANA = "https://apimsbr.ana.gov.br/rpc/v1/dados-tabulares-monitor?tipo_area=1&area=25"
CLASSES = ("S0", "S1", "S2", "S3", "S4")


def baixar(url):
    with urlopen(url, timeout=30) as resposta:
        return resposta.read()


def coletar_exogenas(inicio, fim, diretorio):
    linhas = {}
    texto = baixar(NOAA).decode("ascii")
    for linha in texto.splitlines()[1:]:
        if not linha.strip():
            continue
        ano, mes, *valores = linha.split()
        competencia = date(int(ano), int(mes), 1)
        if inicio <= competencia < fim:
            linhas[competencia] = {"mes": competencia, "nino34_anom_c": float(valores[-1])}
    dados_ana = json.loads(baixar(ANA))["data"]["list"]
    for item in dados_ana:
        mapa = item["mapa"]
        competencia = date(mapa["ano"], mapa["mes"], 1)
        if not inicio <= competencia < fim:
            continue
        linha = linhas.setdefault(competencia, {"mes": competencia})
        linha["monitor_mapa_id"] = mapa["id"]
        linha["monitor_data_criacao"] = mapa["data_criacao"]
        linha["monitor_data_publicacao"] = mapa.get("mmo_data_publicacao")
        por_classe = {a["categoria"]: a["area"] / 100 for a in item["areas"] if a["area"] is not None}
        for classe in CLASSES:
            linha[f"monitor_pb_ge_{classe.lower()}_pct"] = por_classe.get(classe)
    campos = ["mes", "nino34_anom_c", "monitor_mapa_id", "monitor_data_criacao",
              "monitor_data_publicacao", *(f"monitor_pb_ge_{c.lower()}_pct" for c in CLASSES)]
    diretorio.mkdir(parents=True, exist_ok=True)
    with (diretorio / "exogenas_pb_mensal.csv").open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(linhas[mes] for mes in sorted(linhas))


if __name__ == "__main__":
    coletar_exogenas(date(2012, 1, 1), date(2026, 11, 1), Path("data"))
