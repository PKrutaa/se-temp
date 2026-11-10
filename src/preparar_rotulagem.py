"""Prepara uma fila cega para dois anotadores humanos do corpus AESA."""
import csv
import html
import json
from pathlib import Path
import random
import re
import unicodedata
from urllib.parse import urlencode
from urllib.request import urlopen

API = "https://www.aesa.pb.gov.br/wp-json/wp/v2/posts"
TERMOS = re.compile(r"\b(seca|secas|estiagem|racionamento|desabastecimento|escassez|"
                    r"acude|acudes|reservatorio|reservatorios|colapso)\b")


def normalizar(texto):
    sem_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acentos.lower().split())


def listar_publicacoes():
    pagina = 1
    while True:
        parametros = {"_fields": "id,date,modified,link,title", "per_page": 100, "page": pagina,
                      "before": "2026-11-01T00:00:00", "orderby": "date", "order": "asc"}
        with urlopen(f"{API}?{urlencode(parametros)}", timeout=30) as resposta:
            paginas = int(resposta.headers["X-WP-TotalPages"])
            yield from json.load(resposta)
        if pagina >= paginas:
            break
        pagina += 1


def preparar(saida):
    candidatos = {}
    for p in listar_publicacoes():
        titulo = html.unescape(re.sub(r"<[^>]*>", "", p["title"]["rendered"])).strip()
        if titulo:
            candidatos.setdefault(normalizar(titulo), {
                "id_aesa": p["id"], "publicado_em": p["date"], "modificado_em": p["modified"],
                "url": p["link"], "titulo": titulo,
            })
    rng = random.Random(621)
    tem_termo = [item for chave, item in candidatos.items() if TERMOS.search(chave)]
    outros = [item for chave, item in candidatos.items() if not TERMOS.search(chave)]
    relevantes = rng.sample(tem_termo, min(len(tem_termo), 140))
    amostra = relevantes + rng.sample(outros, min(len(outros), 220-len(relevantes)))
    if len(amostra) < 200:
        raise RuntimeError("O corpus retornou menos de 200 candidatos distintos.")
    rng.shuffle(amostra)
    saida.mkdir(parents=True, exist_ok=True)
    campos = ["id_aesa", "publicado_em", "modificado_em", "url", "titulo", "rotulo", "nota"]
    for anotador in (1, 2):
        with (saida / f"anotador_{anotador}.csv").open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=campos)
            escritor.writeheader()
            escritor.writerows(amostra)
    print(f"{len(amostra)} candidatos; {len(relevantes)} com termo de triagem no título.")


if __name__ == "__main__":
    preparar(Path("data/noticias"))
