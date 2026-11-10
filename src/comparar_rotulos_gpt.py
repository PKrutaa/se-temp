"""Compara classificadores sobre uma amostra com referência automática GPT."""
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score

PASTA = Path("data/noticias")
CLASSES = [0, 1, 2]


def comparar():
    ficha = pd.read_csv(PASTA / "anotador_1.csv", usecols=["id_aesa"])
    referencia = pd.read_csv(PASTA / "rotulos_gpt_6_1_sol.csv")
    automaticos = pd.read_csv(PASTA / "classificacao_automatica.csv")

    if len(referencia) != len(ficha) or set(referencia.id_aesa) != set(ficha.id_aesa):
        raise ValueError("A referência GPT deve cobrir exatamente os IDs da ficha.")
    pares = referencia.merge(automaticos, on="id_aesa", validate="1:1")
    if len(pares) != len(ficha):
        raise ValueError("A amostra deve conter predições dos três métodos.")
    for coluna in ("rotulo_gpt", "rotulo_llm", "rotulo_lexical"):
        if not pares[coluna].isin(CLASSES).all():
            raise ValueError(f"Rótulo inválido em {coluna}.")

    y = pares.rotulo_gpt
    resumo = {
        "referencia": {"modelo": "gpt-6.1-sol", "esforco": "medium", "tipo": "automatica"},
        "n": len(pares),
        "classes": CLASSES,
        "suporte_referencia": [int(y.eq(c).sum()) for c in CLASSES],
        "metodos": {},
    }
    for nome, coluna in (("qwen", "rotulo_llm"), ("lexical", "rotulo_lexical")):
        p = pares[coluna]
        resumo["metodos"][nome] = {
            "concordancia_bruta": accuracy_score(y, p),
            "kappa_ponderado_quadratico": cohen_kappa_score(y, p, labels=CLASSES, weights="quadratic"),
            "F1_macro_em_relacao_ao_gpt": f1_score(y, p, labels=CLASSES, average="macro", zero_division=0),
            "matriz_gpt_linhas_metodo_colunas": confusion_matrix(y, p, labels=CLASSES).tolist(),
        }
    return resumo


if __name__ == "__main__":
    resultado = json.dumps(comparar(), ensure_ascii=False, indent=2) + "\n"
    Path("resultados/comparacao_referencia_gpt.json").write_text(resultado, encoding="utf-8")
    print(resultado, end="")
