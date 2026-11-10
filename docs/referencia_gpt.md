# Referência automática com GPT-6.1 Sol

Classificação adicional dos 220 textos da primeira ficha de anotação. O GPT-6.1 Sol, com esforço de raciocínio médio, leu o título e o corpo de cada texto do snapshot AESA. A amostra foi dividida em três lotes disjuntos. Cada texto recebeu um rótulo em uma única passagem, com a rubrica de 0 a 2 e sem acesso às classificações do Qwen ou da regra lexical. As três execuções representam o mesmo modelo e não medem concordância entre anotadores independentes.

- Classe 0: sem ocorrência de seca ou escassez na Paraíba no contexto. Inclui obras, administração ou monitoramento genérico, chuva sem seca e ocorrências em outros estados.
- Classe 1: seca, redução de volume, escassez ou risco na Paraíba sem alerta operacional explícito ou impacto concreto.
- Classe 2: alerta operacional explícito, racionamento, restrição, interrupção, colapso ou impacto concreto da escassez na Paraíba.

As métricas medem a concordância do Qwen e da regra lexical com o GPT na amostra. O F1 macro usa as três classes com o mesmo peso. Nas matrizes de confusão, as linhas correspondem às classes do GPT e as colunas, às classes do método comparado, na ordem 0, 1 e 2. O Qwen e a regra lexical tiveram acesso a até 800 tokens do corpo durante a execução original.

O CSV `data/noticias/rotulos_gpt_6_1_sol.csv` guarda apenas IDs e rótulos. Para recomputar as métricas, rode `python src/comparar_rotulos_gpt.py`. O resultado sai em `resultados/comparacao_referencia_gpt.json`. Esse experimento usa um comparador automático. A validação humana é registrada separadamente pelo validador das fichas.
