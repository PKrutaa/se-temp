from pathlib import Path

from avaliar_noticias import ablar, validar
from modelos import avaliar, dados_modelo, gerar
from selecao import diagnosticar


def executar(raiz=Path(".")):
    dados, volume = dados_modelo(raiz / "data")
    saida = raiz / "resultados"
    lags = diagnosticar(dados, saida)
    print(f"Atrasos em meses: {lags}", flush=True)
    previsoes = gerar(dados, volume, lags)
    metricas, ranking, futuro, dm = avaliar(previsoes, dados, saida)
    previsoes.to_csv(saida / "previsoes_walk_forward.csv.gz", index=False)
    noticias = raiz / "data" / "noticias"
    indice = noticias / "indice_mensal.csv"
    if indice.exists():
        ablar(previsoes, ranking.index[0], indice, saida)
        validar(noticias, saida)
    return metricas, ranking, futuro, dm


if __name__ == "__main__":
    metricas, ranking, futuro, dm = executar()
    print(ranking.to_string())
    print(dm.to_string(index=False))
