# Rotulagem independente de notícias

Os dois CSVs em `data/noticias` são filas iguais, sem rótulos. Cada pessoa lê o conteúdo no link original e preenche seu próprio arquivo, sem consultar o outro anotador nem predições automáticas. A fila de 220 publicações AESA tem positivos e negativos candidatos. O título foi usado para amostrar e o rótulo deve vir da leitura integral.

| Código | Critério |
|---|---|
| 0 | Sem ocorrência de seca/escassez na Paraíba no contexto do texto. Inclui ações administrativas genéricas e referência exclusiva a outros estados. |
| 1 | Descreve seca, redução de volume, risco ou escassez na Paraíba, sem alerta operacional ou impacto concreto identificado. |
| 2 | Reporta alerta operacional explícito, racionamento, restrição, interrupção, colapso de abastecimento ou impacto concreto de escassez na Paraíba. |
| NA | Conteúdo indisponível ou insuficiente para julgar. Escreva o motivo em `nota`. |

Notícia de chuva ou recuperação só recebe 1 ou 2 se o texto trouxer contexto de seca/escassez que satisfaça a classe. Citação histórica sem alerta vigente pode ser classe 1 quando contextualiza diretamente a seca paraibana. Se a localização estiver ambígua, registrar a justificativa. Para cada classe 2, anotar a localidade e o tipo de impacto quando claros. Preencher uma linha por texto. Se houver menos de 200 pares utilizáveis, adicionar candidatos e repetir a rotulagem até atingir a meta.

Calcular concordância bruta e kappa de Cohen ponderado entre os rótulos independentes nos pares válidos. Só depois discutir divergências e gerar uma versão consensual separada. A fila institucional serve à validação piloto. Uma amostra enriquecida por palavras no título não representa a incidência mensal de alarmes. O índice temporal deve ser calculado no corpus coletado sistematicamente e avaliar cobertura por fonte/mês.

Grave as divergências adjudicadas em `data/noticias/consenso.csv` com as colunas `id_aesa,rotulo_consenso`. O validador mede concordância nos pares independentes, agrega os casos concordantes e só calcula F1 macro e matrizes de confusão dos classificadores quando há 200 textos válidos e adjudicados com saída automática. Se candidatos não estiverem presentes no corpus deduplicado, acrescente candidatos classificados e rotulados até atingir a meta.

Os 220 candidatos em cada ficha têm as duas saídas automáticas correspondentes. Essas saídas ficam em arquivo separado das fichas. O excedente de 20 permite substituir textos indisponíveis antes de atingir o mínimo de 200 pares utilizáveis.

Após preencher as fichas e o consenso, execute `python src/avaliar_noticias.py` na raiz do projeto para gerar concordância, F1 macro, métricas por classe e matrizes de confusão sem retreinar os modelos hidrológicos.
