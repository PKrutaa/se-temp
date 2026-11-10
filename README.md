# Seca e açudes da Paraíba

Projeto de Séries Temporais da UFPB, tópico 6. Previsão de volume em porcentagem da capacidade a 3, 4, 5 e 6 meses. O evento crítico é volume estritamente abaixo de 5%.

- [Notebook principal](notebooks/02_projeto_seca_acudes.ipynb) e [especificação](docs/spec.md)
- [Painel tratado consolidado](data/painel_tratado.csv.gz), [dicionário](data/dicionario.md) e [fontes](docs/fontes.md)
- [Métricas por modelo e horizonte](resultados/metricas_modelos.csv), [Diebold–Mariano](resultados/diebold_mariano.csv) e [previsões por açude](resultados/previsoes_modelo_escolhido.csv)
- [Relatório técnico](entregas/Relatorio_Seca_Acudes_PB.pdf) e [slides](entregas/Apresentacao_Seca_Acudes_PB.pptx)
- [Ablação de notícias](resultados/ablacao_noticias.csv) e [auditoria dos rótulos](resultados/validacao_noticias.json)

## Reproduzir

Com Python 3.12, na raiz:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
jupyter execute notebooks/02_projeto_seca_acudes.ipynb --timeout=1800
```

O notebook funciona com os snapshots incluídos, sem consultar a internet. Ele refaz EDA, seleção de atrasos, walk-forward, métricas, previsão e ablação. O ajuste da LSTM usa amostragem fixa de até 5.000 registros elegíveis por origem, cinco épocas e semente 621. A origem de produção é outubro de 2026. O backtest usa a versão retrospectiva das fontes, inclusive de publicações que podem ter sido modificadas após a data original.

O classificador Qwen2.5-1.5B-Instruct quantizado rodou localmente sobre o arquivo de comunicados da AESA. As saídas de inferência, a revisão dos pesos e o prompt estão em `data/noticias`. O notebook reconstitui o índice sobre essas saídas e executa a ablação. Para refazer a inferência a partir do arquivo público, instale `mlx-lm==0.32.2` em um Mac Apple Silicon, baixe a revisão registrada em `data/noticias/modelo.json` e execute `python src/noticias.py --modelo CAMINHO_DA_REVISAO`.

## Atualizar fontes

Os coletores de volumes, SAR, exógenas, clima e mapa local estão em `src`. Os coletores espaciais usam Shapely, PyProj e PyShp. As janelas deste trabalho estão fixadas no snapshot de 2026 e devem ser revistas em uma atualização futura.

## Validação humana das notícias

As duas fichas em `data/noticias` estão preparadas para anotação independente. A classificação automática e a ablação são exploratórias enquanto faltarem pelo menos 200 pares válidos, adjudicação e avaliação por classe. Consulte o [guia de rotulagem](docs/rotulagem.md) para completar a etapa.
