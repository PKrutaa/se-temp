"""Materializa o painel tratado com covariáveis na competência original."""
from pathlib import Path

from modelos import dados_modelo


if __name__ == "__main__":
    dados, _ = dados_modelo(Path("data"))
    if dados.duplicated(["acude_id", "mes"]).any():
        raise ValueError("A chave açude/mês precisa ser única.")
    dados.to_csv("data/painel_tratado.csv.gz", index=False)
