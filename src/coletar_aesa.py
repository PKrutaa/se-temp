"""Constrói um snapshot mensal do painel público da AESA/SEIRA."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

API = "https://seira.aesa.pb.gov.br/api/"
FUSO = ZoneInfo("America/Fortaleza")
COLUNAS = [
    "acude_id", "acude", "municipio", "bacia_id", "bacia", "latitude",
    "longitude", "capacidade_m3", "mes", "data_coleta", "data_envio",
    "volume_m3", "volume_pct", "cota_m", "id_medicao",
]


def obter_json(endpoint, **params):
    url = API + endpoint + "?" + urlencode(params)
    for tentativa in range(3):
        try:
            with urlopen(url, timeout=30) as resposta:
                return json.load(resposta)
        except HTTPError as erro:
            if erro.code not in {429, 500, 502, 503, 504} or tentativa == 2:
                raise
        except (URLError, TimeoutError):
            if tentativa == 2:
                raise
        time.sleep(2 ** tentativa)


def meses_entre(inicio, fim):
    meses = []
    while inicio < fim:
        meses.append(inicio.isoformat())
        inicio = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
    return meses


def coletar_acude(acude_id, inicio, fim, meses):
    consulta = obter_json(
        "historico-reservatorio/por-reservatorio",
        reservatorioId=acude_id,
        dataInicio=inicio.isoformat() + "T00:00:00-03:00",
        dataFim=(fim - timedelta(days=1)).isoformat() + "T23:59:59-03:00",
        periodo="month",
    )
    a = consulta["reservatorio"]
    assert a["id"] == acude_id, (a["id"], acude_id)
    bacia = a.get("bacia") or {}
    municipio = a.get("municipio") or {}
    meta = {
        "acude_id": acude_id, "acude": a["nome"], "municipio": municipio.get("nome"),
        "bacia_id": bacia.get("id"), "bacia": bacia.get("nome"),
        "latitude": a.get("latitude"), "longitude": a.get("longitude"),
        "capacidade_m3": a.get("capacidade"),
    }
    auditoria = Counter()
    observacoes = {}
    for registro in consulta["historico"]:
        coleta = datetime.fromtimestamp(registro["dataColeta"] / 1000, FUSO)
        if not inicio <= coleta.date() < fim:
            auditoria["fora_do_periodo"] += 1
            continue
        pct = registro.get("porcentagem")
        volume = registro.get("volumeAtual")
        if not registro.get("ativo", True) or pct is None or pct < 0 or (
            volume is not None and volume < 0
        ):
            auditoria["invalidas_ou_sem_alvo"] += 1
            continue
        mes = coleta.date().replace(day=1).isoformat()
        anterior = observacoes.get(mes)
        if anterior is not None:
            auditoria["duplicatas_mensais"] += 1
            if (registro["dataColeta"], registro.get("apiId") or 0) <= (
                anterior["dataColeta"], anterior.get("apiId") or 0
            ):
                continue
        observacoes[mes] = registro
    linhas = []
    for mes in meses:
        registro = observacoes.get(mes, {})
        coleta_ms = registro.get("dataColeta")
        linhas.append({
            **meta, "mes": mes,
            "data_coleta": datetime.fromtimestamp(coleta_ms / 1000, FUSO).date() if coleta_ms else None,
            "data_envio": registro.get("dataEnvio"),
            "volume_m3": registro.get("volumeAtual"),
            "volume_pct": registro.get("porcentagem"),
            "cota_m": registro.get("cota"),
            "id_medicao": registro.get("apiId"),
        })
    auditoria.update(meses_observados=len(observacoes), meses_ausentes=len(meses)-len(observacoes))
    return linhas, auditoria


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inicio", type=date.fromisoformat, default=date(2012, 1, 1))
    parser.add_argument("--fim-exclusivo", type=date.fromisoformat, default=date(2026, 11, 1))
    parser.add_argument("--saida", type=Path, default=Path("data"))
    args = parser.parse_args()
    inicio, fim = args.inicio, args.fim_exclusivo
    if inicio.day != 1 or fim.day != 1 or inicio >= fim:
        parser.error("Use primeiros dias de mês, com início anterior ao fim.")
    meses = meses_entre(inicio, fim)
    catalogo = obter_json("reservatorio/listar", nivelEncurtamento="ALTO", filtrarMonitorados="true")
    ids = sorted({item["id"] for item in catalogo})
    if not ids:
        raise RuntimeError("Catálogo AESA vazio.")
    with ThreadPoolExecutor(max_workers=4) as executor:
        resultados = list(executor.map(lambda aid: coletar_acude(aid, inicio, fim, meses), ids))

    args.saida.mkdir(parents=True, exist_ok=True)
    caminho = args.saida / "acudes_mensal.csv"
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        for linhas, _ in resultados:
            escritor.writerows(linhas)
    qualidade = {
        "fonte": API,
        "catalogo_endpoint": "reservatorio/listar?nivelEncurtamento=ALTO&filtrarMonitorados=true",
        "historico_endpoint": "historico-reservatorio/por-reservatorio (periodo=month)",
        "coleta_utc": datetime.now(timezone.utc).isoformat(),
        "inicio_inclusivo": inicio.isoformat(),
        "fim_exclusivo": fim.isoformat(),
        "acudes": len(ids),
        "linhas": len(ids) * len(meses),
        "sha256_csv": hashlib.sha256(caminho.read_bytes()).hexdigest(),
        "por_acude": dict(zip(ids, (auditoria for _, auditoria in resultados))),
    }
    (args.saida / "aesa_auditoria.json").write_text(
        json.dumps(qualidade, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{len(ids)} açudes × {len(meses)} meses = {qualidade['linhas']} linhas em {caminho}")


if __name__ == "__main__":
    main()
