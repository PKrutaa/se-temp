"""Validação humana opcional e ablação temporal de um ajuste aos resíduos."""
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score

from referencia import TESTE_INICIO


def validar(pasta, saida):
    auto = pd.read_csv(pasta / "classificacao_automatica.csv")
    fichas = [pd.read_csv(pasta / f"anotador_{n}.csv")[["id_aesa", "rotulo"]]
              .rename(columns={"rotulo": f"rotulo_{n}"}) for n in (1, 2)]
    pares = fichas[0].merge(fichas[1], on="id_aesa", validate="1:1")
    pares = pares[pares.rotulo_1.isin([0, 1, 2]) & pares.rotulo_2.isin([0, 1, 2])]
    status = {"pares_humanos_validos": len(pares), "minimo": 200}
    if len(pares) >= 200:
        status["concordancia_bruta"] = accuracy_score(pares.rotulo_1, pares.rotulo_2)
        status["kappa_ponderado_quadratico"] = cohen_kappa_score(
            pares.rotulo_1, pares.rotulo_2, weights="quadratic", labels=[0, 1, 2]
        )
        consenso = pasta / "consenso.csv"
        if consenso.exists():
            adjudicado = pd.read_csv(consenso)[["id_aesa", "rotulo_consenso"]]
            pares = pares.merge(adjudicado, on="id_aesa", how="left", validate="1:1")
        else:
            pares["rotulo_consenso"] = np.nan
        pares["rotulo_consenso"] = pares.rotulo_1.where(
            pares.rotulo_1.eq(pares.rotulo_2), pares.rotulo_consenso
        )
        validacao = pares.merge(auto, on="id_aesa", validate="1:1")
        validacao = validacao[validacao.rotulo_consenso.isin([0, 1, 2])]
        status["textos_adjudicados_e_classificados"] = len(validacao)
        if len(validacao) >= 200:
            for nome in ("llm", "lexical"):
                y, p = validacao.rotulo_consenso, validacao[f"rotulo_{nome}"]
                status[nome] = {"F1_macro": f1_score(y, p, average="macro", labels=[0, 1, 2],
                                                     zero_division=0),
                                "confusao": confusion_matrix(y, p, labels=[0, 1, 2]).tolist()}
    status["validacao_humana_concluida"] = "llm" in status
    (saida / "validacao_noticias.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return status


def ablar(previsoes, vencedor, arquivo_indice, saida):
    indice = pd.read_csv(arquivo_indice)
    indice["origem"] = pd.PeriodIndex(indice.pop("mes"), freq="M") + 1
    d = previsoes.loc[previsoes.modelo.eq(vencedor)].merge(indice, on="origem", validate="m:1")
    d = d.dropna(subset=["previsto", "observado", "indice_alarme", "indice_lexical"])
    d["residuo"] = d.observado - d.previsto
    ajustes = []
    for (origem, h), teste in d.loc[d.mes_alvo.ge(TESTE_INICIO)].groupby(["origem", "horizonte"]):
        treino = d.loc[d.mes_alvo.le(origem) & d.horizonte.eq(h)]
        por_origem = treino.groupby("origem")[["residuo", "indice_alarme", "indice_lexical"]].mean()
        if len(por_origem) < 8:
            continue
        e = teste[["acude_id", "origem", "mes_alvo", "horizonte", "observado", "previsto"]].copy()
        e["sem_indice"] = (teste.previsto + por_origem.residuo.mean()).clip(lower=0)
        for nome, variavel in (("com_llm", "indice_alarme"), ("com_lexical", "indice_lexical")):
            modelo = Ridge(alpha=1.0).fit(por_origem[[variavel]], por_origem.residuo)
            e[nome] = (teste.previsto + modelo.predict(teste[[variavel]])).clip(lower=0)
        ajustes.append(e)
    if not ajustes:
        return pd.DataFrame()
    pares = pd.concat(ajustes, ignore_index=True)
    longa = pares.melt(id_vars=["acude_id", "origem", "mes_alvo", "horizonte", "observado"],
                       value_vars=["previsto", "sem_indice", "com_llm", "com_lexical"],
                       var_name="versao", value_name="estimativa")
    longa["erro_abs"] = (longa.observado - longa.estimativa).abs()
    longa["erro_quadrado"] = longa.erro_abs.pow(2)
    tabela = longa.groupby(["versao", "horizonte"]).agg(
        MAE_pp=("erro_abs", "mean"), MSE_pp2=("erro_quadrado", "mean"), n=("acude_id", "size"),
        origens=("origem", "nunique"),
    )
    tabela["RMSE_pp"] = tabela.pop("MSE_pp2").pow(0.5)
    tabela["modelo_base"] = vencedor
    tabela.to_csv(saida / "ablacao_noticias.csv")
    pares.to_csv(saida / "ablacao_pares.csv.gz", index=False)
    return tabela
