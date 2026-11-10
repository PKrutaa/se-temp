"""Gera duas fichas cegas a partir do corpus AESA já classificado."""
import csv
from pathlib import Path
import random
import re
import unicodedata

API = "https://www.aesa.pb.gov.br/wp-json/wp/v2/posts"
TERMOS = re.compile(r"\b(seca|secas|estiagem|racionamento|desabastecimento|escassez|"
                    r"acude|acudes|reservatorio|reservatorios|colapso)\b")
CAMPOS_PUBLICOS = ("id_aesa", "publicado_em", "modificado_em", "url", "titulo")


def normalizar(texto):
    sem_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acentos.lower().split())


def ler(caminho):
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def preparar(pasta):
    candidatos = {r["id_aesa"]: r for r in ler(pasta / "classificacao_automatica.csv")}
    fichas = [pasta / f"anotador_{n}.csv" for n in (1, 2)]
    existentes = [ler(f) if f.exists() else [] for f in fichas]
    if any(r.get("rotulo") or r.get("nota") for ficha in existentes for r in ficha):
        raise ValueError("Há anotações nas fichas. Preserve-as antes de gerar uma nova amostra.")

    if len(candidatos) < 220:
        raise ValueError("O corpus precisa ter pelo menos 220 textos distintos.")
    rng = random.Random(621)
    if existentes[0]:
        ids = list(dict.fromkeys(r["id_aesa"] for r in existentes[0] if r["id_aesa"] in candidatos))
        reserva = sorted(set(candidatos) - set(ids))
        ids = ids[:220] + rng.sample(reserva, max(220 - len(ids), 0))
    else:
        relevantes = [aid for aid, r in candidatos.items() if TERMOS.search(normalizar(r["titulo"]))]
        outros = sorted(set(candidatos) - set(relevantes))
        ids = rng.sample(sorted(relevantes), min(len(relevantes), 140))
        ids.extend(rng.sample(outros, min(len(outros), 220 - len(ids))))
        restantes = sorted(set(relevantes) - set(ids))
        ids.extend(rng.sample(restantes, 220 - len(ids)))
        rng.shuffle(ids)

    amostra = [{campo: candidatos[aid][campo] for campo in CAMPOS_PUBLICOS} for aid in ids]
    for ficha in fichas:
        with ficha.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=[*CAMPOS_PUBLICOS, "rotulo", "nota"])
            escritor.writeheader()
            escritor.writerows(amostra)
    print(f"{len(amostra)} textos do corpus deduplicado disponíveis nas duas fichas.")


if __name__ == "__main__":
    preparar(Path("data/noticias"))
