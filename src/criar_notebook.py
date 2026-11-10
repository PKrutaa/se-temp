"""Gera a versão inicial do notebook com células curtas e módulos compartilhados."""
from pathlib import Path

import nbformat as nbf

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
nb = nbf.v4.new_notebook(cells=[
    md("""# Seca e açudes da Paraíba
Primeira execução. Diagnóstico dos volumes AESA e duas referências temporais para prever horizontes de 3 a 6 meses. As previsões desta versão são provisórias. Consulte a especificação para a comparação final, variáveis externas e experimento de notícias."""),
    code("""from pathlib import Path
import sys
import matplotlib.pyplot as plt
import pandas as pd

raiz = Path.cwd()
if not (raiz / 'data/acudes_mensal.csv').exists():
    raiz = raiz.parent
sys.path.insert(0, str(raiz / 'src'))

from eda import descrever, plotar_stl
from referencia import executar, preparar_painel

base, painel = preparar_painel(raiz / 'data/acudes_mensal.csv')
resumo = pd.Series({
    'açudes': painel.shape[1],
    'meses': painel.shape[0],
    'observações': base.volume_pct.count(),
    'ausências': base.volume_pct.isna().sum(),
    'zeros medidos': base.volume_pct.eq(0).sum(),
    'acima de 100%': base.volume_pct.gt(100).sum(),
    'abaixo de 5%': base.volume_pct.lt(5).sum(),
    'açudes com leitura no último mês': painel.iloc[-1].count(),
})
display(resumo.to_frame('contagem'))"""),
    md("""## Diagnóstico das séries
O alvo original fica intacto. As estatísticas e testes usam a observação publicada. ADF testa a hipótese nula de raiz unitária; KPSS testa estacionariedade em nível. O diagnóstico usa o maior bloco contíguo de cada açude, e o p-valor do KPSS fica limitado à tabela do teste. A STL robusta usa período anual de 12 meses e a figura mostra Acauã, com ID AESA 126."""),
    code("""diagnostico = descrever(base, painel)
display(diagnostico.sort_values('meses_criticos', ascending=False).head(12))
ax = painel[126].plot(figsize=(10, 3), title='Acauã — observações mensais')
ax.set_ylabel('Volume (%)')
ax.axhline(5, color='tab:red', linestyle=':')
plt.show()
figura_stl = plotar_stl(painel[126])
figura_stl.set_size_inches(10, 6)
plt.show()"""),
    md("""## Walk-forward das referências
Persistência usa o valor medido na origem. A referência sazonal usa o valor do mesmo mês no ano anterior ao alvo. A coorte exige 60 meses observados até dezembro de 2022. A avaliação usa a interseção de previsões válidas nos alvos desde janeiro de 2025. Os intervalos são empíricos, com quantis de erros dos alvos de 2023–2024 já observados até cada origem, por horizonte. A simulação usa o snapshot retrospectivo; revisões históricas e disponibilidade efetiva podem afetar a reprodução de uma previsão operacional."""),
    code("""coorte, metricas, previsoes = executar(painel)
print(f'{len(coorte)} açudes na coorte de desenvolvimento.')
display(metricas.round(3))"""),
    md("""## Projeção de referência
Origem no último mês civil completo. O corte é estritamente abaixo de 5%. O CSV mantém estimativas ausentes e intervalos que cruzam o limiar. Ausência de leitura na origem impede persistência, mas pode permitir a referência sazonal."""),
    code("""nomes = base[['acude_id', 'acude']].drop_duplicates()
previsoes = previsoes.merge(nomes, on='acude_id', validate='m:1')
alertas = previsoes.loc[previsoes.critico_pontual.fillna(False)]
display(alertas.groupby(['modelo', 'mes_alvo']).size().rename('alertas').to_frame())
destino = raiz / 'resultados'
destino.mkdir(exist_ok=True)
diagnostico.to_csv(destino / 'diagnostico_acudes.csv', index=False)
metricas.to_csv(destino / 'metricas_referencias.csv', index=False)
previsoes.to_csv(destino / 'previsoes_referencias.csv', index=False)"""),
], metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}})
nbf.write(nb, Path("notebooks/01_volumes_e_referencias.ipynb"))
