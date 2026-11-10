"""Gera o notebook com a sequência integral executável sobre o snapshot."""
from pathlib import Path

import nbformat as nbf

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
nb = nbf.v4.new_notebook(cells=[
    md("""# Seca e açudes da Paraíba
Previsão mensal de volume armazenado a 3, 4, 5 e 6 meses, em porcentagem da capacidade. Um evento crítico exige volume estritamente inferior a 5%. O snapshot termina em outubro de 2026 e está incluído no projeto. A execução não consulta a internet."""),
    code("""from pathlib import Path
import sys

raiz = Path.cwd()
if not (raiz / 'data/acudes_mensal.csv').exists():
    raiz = raiz.parent
sys.path.insert(0, str(raiz / 'src'))

import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.graphics.tsaplots import plot_acf
from eda import auditar_medicoes, bloco_contiguo, descrever, plotar_stl
from executar_modelos import executar
from modelos import dados_modelo
from noticias import indices
from avaliar_noticias import ablar, validar

saida = raiz / 'resultados'
saida.mkdir(exist_ok=True)
base, painel = dados_modelo(raiz / 'data')
assert not base.duplicated(['acude_id', 'mes']).any()
display(pd.Series({
    'açudes': painel.shape[1], 'meses': painel.shape[0],
    'leituras válidas': base.volume_pct.notna().sum(),
    'ausências': base.volume_pct.isna().sum(),
    'zeros medidos': base.volume_pct.eq(0).sum(),
    'leituras críticas': base.volume_pct.lt(5).sum(),
}).to_frame('n'))"""),
    md("""## Dados e análise exploratória
Cada observação conserva a porcentagem publicada pela AESA, inclusive zero e possíveis sangrias acima de 100%. As tabelas sinalizam saltos e divergências da capacidade atual para auditoria. As previsões usam no máximo dois meses de carregamento para o preditor 'último volume'. A ausência de alvo nunca vira uma observação. ADF testa raiz unitária e KPSS testa estacionariedade em nível. Ambos usam o maior bloco contíguo disponível por série."""),
    code("""diagnostico = descrever(base, painel)
diagnostico.to_csv(saida / 'diagnostico_acudes.csv', index=False)
qualidade = auditar_medicoes(base)
qualidade.to_csv(saida / 'auditoria_medicoes.csv.gz', index=False)
display(qualidade.iloc[:, -4:].sum().to_frame('sinalizações'))
display(diagnostico.nlargest(8, 'meses_criticos'))

fig, axs = plt.subplots(2, 1, figsize=(10, 5), constrained_layout=True)
painel.notna().sum(axis=1).plot(ax=axs[0], color='#286A75', title='Açudes com leitura por mês')
axs[0].set_ylabel('Açudes')
ids = [126, *[x for x in diagnostico.nlargest(2, 'meses_criticos').acude_id if x != 126]]
nomes = base.set_index('acude_id').acude.to_dict()
painel[ids].rename(columns=nomes).plot(ax=axs[1], title='Séries observadas')
axs[1].axhline(5, color='#aa4728', linestyle=':')
axs[1].set_ylabel('Volume (%)')
plt.show()

figura = plotar_stl(painel[126])
figura.set_size_inches(10, 6)
plt.show()
x = bloco_contiguo(painel[126])
fig, axs = plt.subplots(1, 2, figsize=(10, 3), constrained_layout=True)
plot_acf(x, lags=24, ax=axs[0], title='Acauã — ACF em nível')
plot_acf(x.diff().dropna(), lags=24, ax=axs[1], title='Acauã — ACF em diferenças')
plt.show()"""),
    md("""## Seleção e protocolo temporal
Desenvolvimento até dez/2022. A triagem calcula Pearson e Spearman em nível e diferenças nos atrasos 0 a 12. A convenção é x(t−lag) contra y(t). Entre atrasos 1 a 6, escolhe o maior |Spearman| mediano das diferenças por covariável e examina VIF com limiar 10. Granger usa o maior bloco contíguo das diferenças e FDR-BH, como diagnóstico de associação preditiva. O atraso mínimo é um mês para exógenas, com controle adicional de criação do mapa do Monitor.

A coorte exige 60 observações até dez/2022. O walk-forward avança a origem mês a mês. Treino direto usa só alvos conhecidos na origem. A ordenação usa MAE médio dos horizontes na validação até jun/2024. Intervalos por horizonte usam erros de calibração disponíveis até cada origem. A simulação é retrospectiva, com o snapshot final das fontes. A LSTM usa cinco épocas e uma amostra aleatória fixa de até 5.000 exemplos disponíveis a cada origem. Os modelos são referências sazonal e persistência, SARIMAX(1,1,0) com parâmetros ajustados no desenvolvimento e atualização do estado, histogram gradient boosting e LSTM global."""),
    code("""metricas, ranking, futuro, dm = executar(raiz)
display(pd.read_csv(saida / 'atrasos_escolhidos.csv').round(3))
display(pd.read_csv(saida / 'vif.csv').round(3))
display(ranking.round(3).to_frame('MAE validação (p.p.)'))"""),
    md("""## Comparação fora do treino
O teste usa alvos de jan/2025 a out/2026 e somente chaves comparáveis. MAPE usa os alvos positivos e sMAPE define 0/0 como zero. MASE usa erro ingênuo sazonal no histórico até cada origem. O Diebold–Mariano usa perda absoluta, média transversal por origem, variância HAC Bartlett, correção de pequena amostra HLN e ajuste de Holm. As 22 origens por horizonte limitam o poder do teste."""),
    code("""display(metricas.round(3))
display(dm.round(3))
fig, axs = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
for nome, grupo in metricas.groupby('modelo'):
    axs[0].plot(grupo.horizonte, grupo.MAE_pp, marker='o', label=nome)
    axs[1].plot(grupo.horizonte, grupo.F1, marker='o')
axs[0].set_ylabel('MAE (p.p.)')
axs[1].set_ylabel('F1 crítico (<5%)')
for ax in axs:
    ax.set_xlabel('Horizonte (meses)')
    ax.set_xticks([3, 4, 5, 6])
axs[0].legend(fontsize=8)
plt.show()"""),
    md("""## Projeções e alertas
O modelo escolhido na validação projeta de jan/2027 a abr/2027 com origem em out/2026. As 131 estações aparecem no arquivo, com marcação de exclusões da coorte e de valores ausentes. Um intervalo que cruza o limiar indica incerteza sobre o alerta pontual."""),
    code("""alertas = futuro.loc[futuro.critico_pontual.fillna(False)]
display(futuro.groupby('mes_alvo').agg(
    com_previsao=('previsto', 'count'), alertas=('critico_pontual', 'sum'),
    intervalos_cruzam_5=('intervalo_cruza_5', 'sum')
))
display(alertas[['acude','mes_alvo','previsto','inferior_90','superior_90','ultima_leitura']]
        .sort_values(['mes_alvo','previsto']).head(30).round(2))"""),
    md("""## Índice de notícias e validação
O índice mensal é a proporção de comunicados AESA classificados na classe 2 pelo Qwen2.5-1.5B-Instruct quantizado. Uma regra lexical fixa serve de comparação. O experimento usa o índice do mês anterior para corrigir resíduos do modelo vencedor, com a mesma amostra para os métodos. O resultado é exploratório enquanto a auditoria de rótulos humanos indicar menos de 200 pares válidos e adjudicados."""),
    code("""import json
pasta_noticias = raiz / 'data/noticias'
classificacoes = pd.read_csv(pasta_noticias / 'classificacao_automatica.csv')
indices(classificacoes).to_csv(pasta_noticias / 'indice_mensal.csv')
pares = pd.read_csv(saida / 'previsoes_walk_forward.csv.gz')
for campo in ['origem', 'mes_alvo']:
    pares[campo] = pd.PeriodIndex(pares[campo], freq='M')
ablar(pares, ranking.index[0], pasta_noticias / 'indice_mensal.csv', saida)
validar(pasta_noticias, saida)
status_noticias = saida / 'validacao_noticias.json'
if status_noticias.exists():
    display(json.loads(status_noticias.read_text(encoding='utf-8')))
ablacao = saida / 'ablacao_noticias.csv'
if ablacao.exists():
    display(pd.read_csv(ablacao).round(3))"""),
], metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}})
nbf.write(nb, Path("notebooks/02_projeto_seca_acudes.ipynb"))
