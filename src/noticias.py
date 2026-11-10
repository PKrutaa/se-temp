"""Classifica todo o arquivo institucional e constrói o índice mensal."""
import argparse
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from preparar_rotulagem import API, normalizar, TERMOS

INSTRUCAO = """Classifique este comunicado institucional sobre a Paraíba em apenas uma categoria.
0: irrelevante para seca ou escassez hídrica na Paraíba. Monitoramento rotineiro, obras genéricas, meteorologia e chuva, sem menção a seca ou escassez no contexto.
1: seca, estiagem, escassez ou risco hídrico na Paraíba, sem alerta operacional ou impacto concreto identificado.
2: alerta operacional explícito, racionamento, restrição de uso, interrupção de abastecimento ou impacto concreto de escassez na Paraíba.
Use o texto como evidência. O título pode ser insuficiente. Responda só 0, 1 ou 2."""
CRITICO = re.compile(r"\b(racionamento|desabastecimento|colapso|restricao de (uso|captacao)|"
                     r"interrupcao (no|de) abastecimento|suspensao (do|de) abastecimento)\b")
SECA = re.compile(r"\b(seca|secas|estiagem|escassez|crise hidrica|baixa disponibilidade|volume morto)\b")


class Texto(HTMLParser):
    def __init__(self):
        super().__init__()
        self.partes = []

    def handle_data(self, data):
        self.partes.append(data)

    @classmethod
    def limpar(cls, html):
        parser = cls()
        parser.feed(html)
        return " ".join(" ".join(parser.partes).split())


def consultar(cache):
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    pagina = 1
    saida = []
    while True:
        params = {"_fields": "id,date,modified,link,title,content", "per_page": 100, "page": pagina,
                  "before": "2026-11-01T00:00:00", "orderby": "date", "order": "asc"}
        with urlopen(f"{API}?{urlencode(params)}", timeout=60) as r:
            paginas = int(r.headers["X-WP-TotalPages"])
            saida.extend(json.load(r))
        if pagina >= paginas:
            break
        pagina += 1
    cache.parent.mkdir(exist_ok=True, parents=True)
    cache.write_text(json.dumps(saida, ensure_ascii=False), encoding="utf-8")
    return saida


def corpus(registros):
    titulos, hashes = set(), set()
    for r in registros:
        titulo = Texto.limpar(r["title"]["rendered"])
        corpo = Texto.limpar(r["content"]["rendered"])
        chave = normalizar(titulo)
        hash_corpo = sha256(normalizar(corpo).encode()).hexdigest()
        if not chave or len(corpo) < 40 or chave in titulos or hash_corpo in hashes:
            continue
        titulos.add(chave)
        hashes.add(hash_corpo)
        yield {"id_aesa": r["id"], "publicado_em": r["date"], "modificado_em": r["modified"],
               "url": r["link"], "titulo": titulo, "caracteres": len(corpo),
               "sha256_texto_normalizado": hash_corpo, "corpo": corpo}


def classe_lexical(texto):
    texto = normalizar(texto)
    if CRITICO.search(texto) and TERMOS.search(texto):
        return 2
    return 1 if SECA.search(texto) else 0


def classificar(registros, caminho_modelo):
    import mlx.core as mx
    from mlx_lm import load

    modelo, tokenizer = load(str(caminho_modelo))
    ids_classe = []
    for classe in range(3):
        variantes = [tokenizer.encode(t, add_special_tokens=False) for t in (str(classe), f" {classe}")]
        ids_classe.append([ids[0] for ids in variantes if len(ids) == 1])
    for i, registro in enumerate(registros, 1):
        corpo = registro.pop("corpo")
        tokens = tokenizer.encode(corpo, add_special_tokens=False)
        trecho = tokenizer.decode(tokens[:800])
        texto = f"{registro['titulo']}\n{trecho}"
        conversa = [
            {"role": "system", "content": INSTRUCAO},
            {"role": "user", "content": f"Título e texto do comunicado:\n{texto}"},
        ]
        prompt = tokenizer.apply_chat_template(conversa, tokenize=False, add_generation_prompt=True)
        codigos = tokenizer.encode(prompt, add_special_tokens=False)
        # Only project the final hidden state. Earlier token logits are unused.
        estado = modelo.model(mx.array([codigos]))[:, -1, :]
        projetar = modelo.model.embed_tokens.as_linear if modelo.args.tie_word_embeddings else modelo.lm_head
        logits = projetar(estado)[0]
        escores = mx.stack([mx.max(logits[mx.array(ids)]) for ids in ids_classe])
        probs = mx.softmax(escores).tolist()
        classe = max(range(3), key=probs.__getitem__)
        yield {**registro, "rotulo_llm": classe, "escore_restrito": probs[classe],
               "rotulo_lexical": classe_lexical(texto), "truncado": len(tokens) > 800}
        if i % 50 == 0:
            print(f"{i} textos classificados", flush=True)


def indices(rotulos):
    d = rotulos.assign(mes=pd.to_datetime(rotulos.publicado_em).dt.to_period("M"),
                        alarme_llm=rotulos.rotulo_llm.eq(2), alarme_lexical=rotulos.rotulo_lexical.eq(2))
    indice = d.groupby("mes").agg(textos=("id_aesa", "size"), alarmes_llm=("alarme_llm", "sum"),
                                 alarmes_lexical=("alarme_lexical", "sum"))
    indice = indice.reindex(pd.period_range(d.mes.min(), "2026-10", freq="M")).rename_axis("mes")
    indice["indice_alarme"] = indice.alarmes_llm / indice.textos
    indice["indice_lexical"] = indice.alarmes_lexical / indice.textos
    return indice


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--modelo", type=Path, required=True)
    p.add_argument("--cache", type=Path, default=Path("../corpus_aesa.json"))
    args = p.parse_args()
    registros = list(corpus(consultar(args.cache)))
    checkpoint = args.cache.with_name(f"{args.cache.stem}-{args.modelo.name}.jsonl")
    anteriores = {}
    if checkpoint.exists():
        for linha in checkpoint.read_text(encoding="utf-8").splitlines():
            item = json.loads(linha)
            anteriores[(item["id_aesa"], item["sha256_texto_normalizado"])] = item
    restantes = [r for r in registros if (r["id_aesa"], r["sha256_texto_normalizado"]) not in anteriores]
    with checkpoint.open("a", encoding="utf-8", buffering=1) as arquivo:
        for item in classificar(restantes, args.modelo):
            chave = (item["id_aesa"], item["sha256_texto_normalizado"])
            anteriores[chave] = item
            arquivo.write(json.dumps(item, ensure_ascii=False) + "\n")
    dados = pd.DataFrame(anteriores[(r["id_aesa"], r["sha256_texto_normalizado"])] for r in registros)
    pasta = Path("data/noticias")
    dados.to_csv(pasta / "classificacao_automatica.csv", index=False)
    indices(dados).to_csv(pasta / "indice_mensal.csv")
    (pasta / "modelo.json").write_text(json.dumps({
        "repositorio": "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        "revisao": args.modelo.name, "prompt": INSTRUCAO, "tokens_max_corpo": 800,
        "decodificacao": "argmax entre rótulos 0, 1 e 2 no primeiro token",
        "fonte": API, "limite_publicacao_exclusivo": "2026-11-01"
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(dados[["rotulo_llm", "rotulo_lexical"]].apply(pd.Series.value_counts))


if __name__ == "__main__":
    main()
