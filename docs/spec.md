# Seca e açudes da Paraíba

## Escopo e entrega

Projeto de Séries Temporais, tópico 6. O enunciado fornecido pelo aluno indica entrega em 10/11/2026 e apresentação em 11/11/2026 na sala da Zoox, com 20 minutos de exposição e 10 de perguntas. Datas registradas como contexto fornecido, pendentes de confirmação ao vivo no SIGAA.

Pergunta principal: qual a porcentagem da capacidade armazenada em cada açude elegível daqui a 3, 4, 5 e 6 meses? Em quais meses e açudes a estimativa pontual cai estritamente abaixo de 5%? Publicar também a faixa de previsão e distinguir alerta pontual, faixa que cruza o limiar e ausência de dados. O universo começa no catálogo monitorado pela AESA e termina na coorte com informação suficiente. Listar exclusões e seus motivos.

## 1. Dados e rastreabilidade

- Obter o catálogo e a série mensal pelo painel público [AESA/SEIRA](https://seira.aesa.pb.gov.br/dados-hidrologicos/monitoramento/volume-reservatorios). Alinhar 2012-01 ao último mês civil completo, em America/Fortaleza. Em cada açude/mês usar o último registro mensal válido devolvido pela fonte, conservar data real, volume, cota, capacidade de referência, ID, município e bacia. Conservar porcentagem publicada e checar diferenças contra a razão volume/capacidade. Registrar unidades, datas, URL/parâmetros, versão e checksums.
- Usar [ANA/SAR](https://www.ana.gov.br/sar0/Medicao) para conferência independente em açudes pareados por nome e metadados. Comparar datas/medidas coincidentes, relatar divergências e manter a série AESA como principal. Identificadores de uma fonte não equivalem aos da outra.
- Painel retangular com chave única açude/mês. Preservar zeros medidos e valores acima de 100% compatíveis com sangria. Campos ausentes permanecem NA, e negativos, duplicatas conflitantes, medições antigas dentro do mês e saltos entram na auditoria. Não preencher alvo de avaliação. Documentar a diferença entre data de coleta, data de envio e data efetivamente disponível. Tratar a ausência de versões históricas como limitação do backtest retrospectivo.
- Integrar chuva agregada por área da bacia quando houver geometria e grade/série adequada, temperatura média mensal, evaporação ou ET₀ identificada como proxy, índice Niño 3.4, capacidade e uso documentado, e categoria mensal da [ANA/Monitor de Secas](https://monitordesecas.ana.gov.br/dados-sig). Se a chuva for pontual ou média de estações sem ponderação de área, usar coluna e descrição próprias. Ausência de mapa é diferente de área sem seca. Registrar disponibilidade e defasagem de publicação por fonte. Capacidade de cadastro atual entra como metadado estático, com ressalva de mudanças históricas; uso/outorga não equivale a retirada medida.
- Entregáveis de dados: CSV mensal, catálogo, dicionário com tipo/unidade/fonte/frequência/cobertura e registro de qualidade. Incluir snapshot para execução offline e instruções separadas de atualização.

## 2. EDA e seleção de variáveis

- Tabelas de cobertura, tamanho das lacunas, min/mediana/máx, amplitude, dispersão, frequência de meses críticos e mudanças de capacidade quando identificáveis. Gráficos de séries, calendário de faltas, histograma e exemplos que representem litoral, semiárido e episódios críticos.
- STL robusta com período 12 em blocos contíguos com pelo menos 36 meses. ADF e KPSS com hipóteses explícitas, e ACF dos níveis e diferenças. Expor conflito entre testes, tamanhos amostrais e séries inelegíveis. Não suavizar seca ou sangria. Qualquer preenchimento de preditores no modelo deve usar só informação anterior ao corte.
- Em dados de desenvolvimento, Pearson/Spearman e correlação cruzada nos atrasos 0–12, com convenção explícita de sinal e verificação nas diferenças para evitar sazonalidade compartilhada. Testar Granger nas diferenças para atrasos de 1 a 6 com ajuste de múltiplos testes e declarar efeito preditivo sem inferência causal. Medir VIF no conjunto candidato e remover redundâncias de forma documentada.
- Decidir atraso por fonte em validação temporal, registrando janela, unidade, transformação, frequência de seleção e ganho fora do treino. Candidatos autorregressivos: atrasos 0, 1, 2, 3, 6 e 12 a partir da origem, diferenças e sazonalidade. Manter fixas as decisões durante o teste final.

## 3. Modelagem e validação

- Referência ingênua sazonal, SARIMAX, XGBoost e LSTM global compartilhada entre açudes. Acrescentar persistência como diagnóstico se o custo for baixo. Selecionar ordem/hiperparâmetros em desenvolvimento, registrar sementes, versões e orçamento. Se houver substituição, manter quatro modelos em três famílias e motivá-la.
- Origem mensal, janela expansiva, horizontes 3–6, a mesma coorte e interseção de chaves válidas para comparação. Planejamento inicial: desenvolvimento até 2022-12, validação em 2023–2024 para seleção/calibração e alvos de teste em 2025-01 até o último mês fechado disponível. Restringir exemplos de treinamento aos alvos já conhecidos na origem, inclusive nas tarefas diretas. Congelar regras antes de analisar o teste e registrar qualquer ajuste de calendário.
- SARIMAX usa histórico de volume; incluir exógenas apenas quando o caminho futuro for conhecido na origem ou estimado a partir do passado. XGBoost e LSTM usam previsões diretas por horizonte com covariáveis disponíveis na origem. Escalonamento aprendido no treino. Sem atualização com alvos futuros, interpolação retrospectiva no backtest ou uso de chuva, notícias e categorias realizadas depois do corte.
- Coorte inicial: pelo menos 60 observações de desenvolvimento e presença suficiente para modelagem. Reportar cobertura por modelo, açude e horizonte e comparar em chaves comuns. Para projeção operacional, informar o mês-base e excluir ou marcar açudes sem medição recente.

## 4. Métricas e previsão final

- MAE e RMSE em pontos percentuais, MAPE nos alvos estritamente positivos com denominador e contagem explícitos, e WAPE ou sMAPE como alternativa com zeros e tratamento explícito do caso ambos zero. MASE com denominador ingênuo sazonal de 12 meses por açude/origem calculado apenas no treino; reportar casos indefinidos. Mostrar suporte e erros por horizonte, agrupamento macro por açude e pares comparáveis.
- Criticidade estrita y < 5%. Calcular matriz de confusão, precisão, recall e F1 com suporte de positivos, por horizonte e no total. Reportar desempenho de episódios críticos mesmo se raros. Publicar previsão pontual, intervalo, alvo temporal, última observação e flag de risco por açude/horizonte.
- Intervalos empíricos de 90% a partir dos erros fora do treino da calibração, estratificados por horizonte, com largura, cobertura observada e limitações. Não supor independência entre origens ou açudes.
- Comparar os dois modelos pré-selecionados na validação com Diebold–Mariano por horizonte, perda absoluta e média transversal por origem, sobre chaves pareadas. Usar variância HAC para sobreposição, relatar número de origens e tratar amostra pequena, variância degenerada e multiplicidade de horizontes.

## 5. Notícias e LLM

- Coletar corpus público sobre seca/racionamento na Paraíba, com ID, URL, data publicada, fonte, localidade, consulta e disponibilidade mensal. Deduplicar republicações e separar mês sem coleta de mês com zero textos alarmantes. Guardar metadados, rótulos e referências; respeitar condições de redistribuição do texto.
- Duas pessoas rotulam independentemente pelo menos 200 textos distintos da Paraíba, usando instrução fixa, sem ver predições do LLM. Classes iniciais: 0 irrelevante, 1 seca/escassez em contexto, 2 alerta operacional com impacto/racionamento concreto. Versionar guia, registros independentes, adjudicação e contagem. Medir concordância bruta e kappa ponderado antes da adjudicação.
- Comparar LLM de prompt/modelo congelados com regra lexical pré-definida, ou TF–IDF com validação separada, em dados rotulados retidos por tempo e deduplicados. Relatar F1 macro, confusão e suporte. Guardar respostas estruturadas e registrar falhas. Não apresentar classificação automática como anotação humana.
- Construir índice mensal, inicialmente proporção de textos classe 2 entre textos elegíveis deduplicados, com volume de artigos e indicador de ausência de cobertura. Se localização confiável, experimentar índice por região; caso contrário usar estadual. Refazer o melhor modelo com e sem a variável disponível na origem, mantendo janela, coorte, cortes e métricas idênticos. Se não houver 200 textos rotulados por pessoas, identificar o requisito como pendente, mesmo com a coleta e o código prontos.

## 6. Artefatos e critérios de aceite

| Entrega | Aceite |
|---|---|
| Notebook Python | Executa do início ao fim em ambiente limpo usando snapshot e dependências registradas; produz EDA, seleção, métricas, teste, previsão e diagnósticos, com células de explicação. |
| Base e dicionário | Chave única, frequência mensal, datas e fontes por variável, unidades, períodos e contagens verificáveis; zero e NA distintos. |
| Slides | Apresentação de 20 min com mapa/coorte, dados, EDA, método, comparação, incerteza, lista de risco e bloco de notícias; reservar 10 min para perguntas. |
| Relatório | PDF até oito páginas; contexto, dados, métodos, resultados, comparação, alertas, notícias, limitações e link para reprodução. |

Ordem de execução: validar volumes e fechar snapshot; obter exógenas e preparar o corpus/rótulos em paralelo; executar EDA e modelos; gerar previsões e artefatos a partir das tabelas; reexecutar em ambiente limpo e conferir o PDF, os slides e a entrega. Só marcar uma etapa concluída com saída ou evidência verificável.
