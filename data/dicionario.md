# Dicionário do painel mensal

O arquivo consolidado `painel_tratado.csv.gz` liga as tabelas de volume, clima e Monitor pelas chaves descritas abaixo. As covariáveis estão na competência original. Os atrasos e o controle de disponibilidade são aplicados na modelagem. `monitor_catalogo_mes` é a competência do carimbo de criação do mapa no catálogo ANA.

Snapshot de janeiro de 2012 a outubro de 2026. Uma linha por açude monitorado e mês, mesmo quando falta medição. A fonte é o [SEIRA/AESA](https://seira.aesa.pb.gov.br/dados-hidrologicos/monitoramento/volume-reservatorios). O JSON de auditoria registra período, endpoint e SHA-256 do CSV.

| Variável | Definição e unidade | Frequência na fonte |
|---|---|---|
| acude_id | Identificador inteiro do SEIRA | Cadastro |
| acude | Nome do reservatório | Cadastro |
| municipio | Município de cadastro | Cadastro |
| bacia_id | Identificador da bacia/região hidrológica no SEIRA | Cadastro |
| bacia | Nome da bacia/região hidrológica | Cadastro |
| latitude | Coordenada do açude, graus decimais | Cadastro |
| longitude | Coordenada do açude, graus decimais | Cadastro |
| capacidade_m3 | Capacidade nominal atual do cadastro, m³ | Cadastro atual, repetido no painel |
| mes | Primeiro dia do mês civil em America/Fortaleza, ISO 8601 | Mensal |
| data_coleta | Dia da leitura retornada pelo agregador mensal, ISO 8601 local | Mensal, data efetiva da observação |
| data_envio | Carimbo de envio da API com fuso, quando disponível | Registro |
| volume_m3 | Volume armazenado, m³ | Mensal |
| volume_pct | Porcentagem oficial do volume armazenado, em % | Mensal |
| cota_m | Cota do nível de água, m | Mensal |
| id_medicao | Identificador da medição no sistema, quando disponível | Mensal |

Os campos de medição ficam vazios quando o mês não tem observação válida na resposta. Zero é uma leitura. Valores acima de 100% são preservados. O agregador pode devolver uma medição anterior ao fim do mês, e seu comportamento com a última medição inválida não foi validado contra todas as leituras diárias. O campo data_envio pode indicar migração ou revisão posterior, sem comprovar quando a medição se tornou pública. A capacidade é a do cadastro consultado e pode divergir da capacidade vigente na data da leitura. As tabelas explicativas e suas chaves são descritas abaixo.

## Tabela mensal estadual

A tabela `exogenas_pb_mensal.csv` usa a mesma chave mensal `mes` e pode ser ligada a cada açude pela competência. Os valores do Monitor são estaduais. A classificação local é fornecida em tabela separada. Ambas são candidatas na seleção de variáveis.

| Variável | Unidade e definição | Frequência e período | Fonte |
|---|---|---|---|
| nino34_anom_c | Anomalia de temperatura do mar na região Niño 3.4, °C | Mensal, jan/2012–out/2026 | [NOAA/CPC](https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices) |
| monitor_pb_ge_s0_pct a monitor_pb_ge_s4_pct | % da área da Paraíba em classe igual ou superior ao limiar | Mensal, jul/2014–set/2026 | [ANA/Monitor de Secas](https://monitordesecas.ana.gov.br/dados-tabulares?tipo=1&area=25) |
| monitor_mapa_id | Identificador do mapa final no catálogo | Mensal, conforme cobertura do Monitor | ANA |
| monitor_data_criacao | Data e hora de criação do registro no catálogo | Mensal, conforme cobertura do Monitor | ANA |
| monitor_data_publicacao | Data da publicação quando preenchida no catálogo | Mensal, conforme cobertura do Monitor | ANA |

O arquivo NOAA pode conter revisões retrospectivas. Para usar essas séries como preditores, exigir disponibilidade na origem. Data de criação não comprova publicação e serve como controle adicional. O arquivo `ana_aesa_acaua.csv` é uma conferência separada por data de coleta, com porcentagens em % e diferenças em pontos percentuais. As colunas com sufixo `_hm3_sar` estão em hm³. Os IDs usados na conferência são 126 (AESA) e 12005 (ANA).

## Clima por região hidrográfica

`clima_bacias_mensal.csv` tem chave única `bacia_id, mes`, 15 regiões e 178 meses. O [NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/) distribui a reanálise MERRA-2 em grade de 0,5° latitude × 0,625° longitude. A extração verificou as unidades declaradas pelo serviço. As séries têm cobertura de jan/2012 a set/2026. Outubro está vazio por atraso na fonte.

| Variável | Unidade e método | Fonte |
|---|---|---|
| chuva_mm | Precipitação mensal, mm. Média diária corrigida × dias do mês, média das células ponderada por área. | NASA POWER, PRECTOTCORR |
| temperatura_c | Temperatura mensal a 2 m, °C. Média ponderada pela área. | NASA POWER, T2M |
| et_fluxo_mj_m2_dia | Fluxo de energia associado à evapotranspiração, MJ/m²/dia. Proxy de evapotranspiração. | NASA POWER, EVPTRNS |
| celulas | Número de células que intersectam a região. | Cálculo próprio |
| latitude_celula, longitude_celula, area_m2 | Centro da célula em graus e área de interseção em m², no arquivo `clima_pesos_merra2.csv`. | Grade NASA e camadas AESA |

Geometrias das bacias, sub-bacias e regiões dos rios obtidas do [Geoportal da AESA](https://geoportal.aesa.pb.gov.br/arquivos/arquivos-shapefiles/). A região Seridó agrega as sub-bacias Oriental e Ocidental. A bacia/trecho de cadastro pode abranger área além da drenagem a montante do açude. A grade é grossa para reservatórios pequenos. A capacidade de cadastro serve como variável estática e não há retiradas mensais neste painel.

## Notícias institucionais

`noticias/classificacao_automatica.csv` identifica o comunicado por `id_aesa`, URL, título, data publicada e data de modificação no [arquivo AESA](https://www.aesa.pb.gov.br/wp-json/wp/v2/posts). Guarda hash e comprimento do texto normalizado, classe de 0 a 2, escore do token restrito do LLM e classe lexical. `truncado` indica que a análise usou o início do corpo, limitado a 800 tokens. As saídas dos classificadores são automáticas. As fichas dos anotadores mantêm rótulos humanos separados.

`noticias/indice_mensal.csv` é estadual e registra `textos`, `alarmes_llm`, `alarmes_lexical` e as proporções `indice_alarme` e `indice_lexical`. As proporções ficam vazias em meses sem texto elegível. Competência pela data de publicação. A ablação consulta a competência anterior e usa o arquivo contemporâneo, que pode trazer revisões posteriores. O corpus tem viés institucional e cobertura irregular.

## Categoria do Monitor no ponto do açude

`monitor_local_mensal.csv` tem chave `acude_id, mes`. A coluna `monitor_local_severidade` identifica a classe geográfica do [Monitor de Secas da ANA](https://monitordesecas.ana.gov.br/dados-sig) no ponto de cadastro. Valores 0 a 4 correspondem a S0 a S4. −1 indica o polígono de fundo SI sem classe de seca sobreposta. Ausência indica falta de cobertura do ponto ou falha de leitura da camada. Em sobreposições, prevalece a maior severidade. Os mapas disponíveis vão de jul/2014 a set/2026. `monitor_local_auditoria.csv` identifica as camadas, as falhas e a contagem de pontos por mapa.
