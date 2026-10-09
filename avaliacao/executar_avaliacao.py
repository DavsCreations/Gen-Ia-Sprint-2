"""
Avaliação do GenIA: qualidade da recuperação, decisão de escopo, classificador de intenção,
validador de respostas, comportamento ponta a ponta e consistência das respostas.

Uso:
    python -m avaliacao.executar_avaliacao               # avalia no modo configurado (.env)
    python -m avaliacao.executar_avaliacao --rapido      # pula a comparação entre configurações
    python -m avaliacao.executar_avaliacao --pausa 2.5   # pausa entre chamadas (limite de uso do LLM)

Grava avaliacao/resultados/<modo>.json e regenera docs/avaliacao.md.
Devolve código de saída 1 se algum critério mínimo não for atingido (usado na integração contínua).
"""
import argparse
import itertools
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline

from app import agentes, config, intencao, llm, prompts, validador
from app.data_loader import Chunk, carregar_relatorio, criar_chunks
from app.rag import BaseVetorial, Trecho, carregar_glossario, gerar_embeddings, preparar_base_vetorial
from app.texto import normalizar

DIR = Path(__file__).parent
DIR_RESULTADOS = DIR / "resultados"
MODELO_SPRINT2 = "sentence-transformers/all-MiniLM-L6-v2"

TIPOS_NO_ESCOPO = ("direta", "parafrase", "leiga")
TIPOS_SEM_COBERTURA = ("tema_ausente", "fora_escopo")

# Critérios mínimos: abaixo disso a avaliação falha e a integração contínua bloqueia a entrega.
CRITERIOS = {
    "recuperacao_acerto_top3": 0.90,
    "pipeline_acuracia_status": 0.85,
    "pipeline_vazamentos": 0,
    "validador_defeitos_detectados": 0.90,
    "validador_falsas_reprovacoes_max": 1,
}


def carregar_perguntas() -> List[Dict[str, Any]]:
    with open(DIR / "conjunto_avaliacao.json", "r", encoding="utf-8") as arquivo:
        perguntas = json.load(arquivo)["perguntas"]

    treino = {normalizar(t) for t in intencao.carregar_exemplos()[0]}
    repetidas = [p["pergunta"] for p in perguntas if normalizar(p["pergunta"]) in treino]
    if repetidas:
        raise SystemExit(f"Perguntas de avaliação presentes no treino do classificador: {repetidas}")
    return perguntas


def chunks_sprint2(relatorio: Dict[str, Any]) -> List[Chunk]:
    """
    Reproduz o chunking da Sprint 2, inclusive o defeito: a chave "composição" (com acento)
    não existe no JSON, então os percentuais de ancestralidade nunca eram indexados.
    """
    chunks = [Chunk("ancestralidade:visao-geral", "", "", relatorio["ancestralidade"]["resumo"])]
    for item in relatorio["ancestralidade"].get("composição", []):
        chunks.append(Chunk(f"ancestralidade:{item['origem']}", "", "", str(item)))
    atuais = {c.tema: c.id for c in criar_chunks(relatorio)}
    for secao in ("saude_genetica", "bem_estar"):
        for item in relatorio[secao]:
            texto = (
                f"Tema: {item.get('tema')}\nResultado: {item.get('resultado')}\n"
                f"Explicação técnica: {item.get('explicacao_tecnica')}\n"
                f"Explicação simples: {item.get('explicacao_simples')}\n"
                f"Recomendação: {item.get('recomendacao')}\n"
            )
            chunks.append(Chunk(atuais[item["tema"]], "", item["tema"], texto))
    for i, aviso in enumerate(relatorio["disclaimers"]):
        chunks.append(Chunk(f"avisos:limites-do-relatorio~{i}", "", "", aviso))
    return chunks


def media(valores: List[float]) -> float:
    return round(float(np.mean(valores)), 3) if valores else 0.0


# ------------------------------------------------------------------ 1. recuperação

def medir_recuperacao(base: BaseVetorial, perguntas: List[Dict[str, Any]]) -> Dict[str, Any]:
    no_escopo = [p for p in perguntas if p["tipo"] in TIPOS_NO_ESCOPO]
    posicoes, pontuacoes_dentro, erros = [], [], []
    por_tipo: Dict[str, List[int]] = {}

    for p in no_escopo:
        aceitas = {p["fonte"], *p.get("fontes_aceitas", [])}
        trechos = base.buscar(p["pergunta"], 3)
        ids = [t.chunk.id.split("~")[0] for t in trechos]
        posicao = next((i + 1 for i, id_chunk in enumerate(ids) if id_chunk in aceitas), 0)
        posicoes.append(posicao)
        pontuacoes_dentro.append(trechos[0].score)
        por_tipo.setdefault(p["tipo"], []).append(int(posicao == 1))
        if posicao != 1:
            erros.append({"id": p["id"], "pergunta": p["pergunta"], "esperado": p["fonte"], "obtido": ids})

    fora = [p for p in perguntas if p["tipo"] in TIPOS_SEM_COBERTURA]
    pontuacoes_fora = [base.buscar(p["pergunta"], 1)[0].score for p in fora]
    rotulos = [1] * len(pontuacoes_dentro) + [0] * len(pontuacoes_fora)

    return {
        "perguntas": len(no_escopo),
        "acerto_top1": media([int(pos == 1) for pos in posicoes]),
        "acerto_top3": media([int(pos > 0) for pos in posicoes]),
        "mrr": media([1 / pos if pos else 0 for pos in posicoes]),
        "acerto_top1_por_tipo": {tipo: media(v) for tipo, v in por_tipo.items()},
        "separacao_auc": round(float(roc_auc_score(rotulos, pontuacoes_dentro + pontuacoes_fora)), 3),
        "erros_top1": erros,
    }


def avaliar_recuperacao(perguntas: List[Dict[str, Any]], rapido: bool) -> List[Dict[str, Any]]:
    relatorio = carregar_relatorio()
    atuais, glossario = criar_chunks(relatorio), carregar_glossario()

    configuracoes = [
        ("Sprint 2 (original)", dict(chunks=chunks_sprint2(relatorio), nome_modelo=MODELO_SPRINT2, indexar_passagens=False, peso_lexical=0)),
        ("+ chunks corrigidos", dict(chunks=atuais, nome_modelo=MODELO_SPRINT2, indexar_passagens=False, peso_lexical=0)),
        ("+ embedding multilíngue", dict(chunks=atuais, nome_modelo=config.MODELO_EMBEDDING, indexar_passagens=False, peso_lexical=0)),
        ("+ passagens curtas", dict(chunks=atuais, nome_modelo=config.MODELO_EMBEDDING, indexar_passagens=True, peso_lexical=0)),
        ("+ busca lexical e glossário (final)", dict(chunks=atuais, nome_modelo=config.MODELO_EMBEDDING, indexar_passagens=True, peso_lexical=config.PESO_LEXICAL, glossario=glossario)),
    ]
    if rapido:
        configuracoes = configuracoes[-1:]

    resultados = []
    for nome, parametros in configuracoes:
        print(f"  recuperação: {nome}")
        resultados.append({"configuracao": nome, **medir_recuperacao(BaseVetorial(**parametros), perguntas)})
    return resultados


# ------------------------------------------------------------------ 2. limiar de escopo

def calibrar_limiar(perguntas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Decisão de escopo: o relatório cobre a pergunta? Compara a decisão só pelo limiar de
    pontuação com a regra em uso (limiar + âncora lexical, agentes.avaliar_cobertura).
    """
    base = preparar_base_vetorial()
    dados = []
    for p in perguntas:
        if p["tipo"] in TIPOS_NO_ESCOPO + TIPOS_SEM_COBERTURA:
            trechos = base.buscar(p["pergunta"], 1)
            dados.append({
                "particao": p["particao"], "no_escopo": p["tipo"] in TIPOS_NO_ESCOPO,
                "score": trechos[0].score, "regra_em_uso": agentes.avaliar_cobertura(trechos)[0],
            })

    def medir(particao: str, decidir) -> Dict[str, Any]:
        linhas = [d for d in dados if d["particao"] == particao]
        dentro = [decidir(d) for d in linhas if d["no_escopo"]]
        fora = [decidir(d) for d in linhas if not d["no_escopo"]]
        return {
            "acuracia_balanceada": round((sum(dentro) / len(dentro) + (len(fora) - sum(fora)) / len(fora)) / 2, 3),
            "falsas_recusas": len(dentro) - sum(dentro),
            "respostas_indevidas": sum(fora),
            "no_escopo": len(dentro), "sem_cobertura": len(fora),
        }

    candidatos = [round(float(x), 2) for x in np.arange(0.20, 0.71, 0.01)]
    curva = [{"limiar": c, **medir("calibracao", lambda d, c=c: d["score"] >= c)} for c in candidatos]
    melhor = max(c["acuracia_balanceada"] for c in curva)
    empatados = [c["limiar"] for c in curva if c["acuracia_balanceada"] == melhor]
    particoes = list(dict.fromkeys(d["particao"] for d in dados))

    return {
        "limiar_recomendado": round(float(np.median(empatados)), 2),
        "faixa_equivalente": [min(empatados), max(empatados)],
        "limiar_em_uso": config.SCORE_MINIMO,
        "semantico_sem_ancora": config.SEMANTICO_SEM_ANCORA,
        "apenas_limiar": {p: medir(p, lambda d: d["score"] >= config.SCORE_MINIMO) for p in particoes},
        "limiar_e_ancora_lexical": {p: medir(p, lambda d: d["regra_em_uso"]) for p in particoes},
        "curva": [c for c in curva if round(c["limiar"] * 100) % 5 == 0],
        "pontuacoes": {
            "no_escopo_minima": min(d["score"] for d in dados if d["no_escopo"]),
            "sem_cobertura_maxima": max(d["score"] for d in dados if not d["no_escopo"]),
        },
    }


def avaliar_peso_lexical(perguntas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Acerto da recuperação para diferentes pesos da busca lexical, por partição."""
    chunks, glossario = criar_chunks(carregar_relatorio()), carregar_glossario()
    linhas = []
    for peso in (0.0, 0.25, 0.5, 0.75, 1.0):
        base = BaseVetorial(chunks, glossario=glossario, peso_lexical=peso)
        linha: Dict[str, Any] = {"peso": peso, "em_uso": peso == config.PESO_LEXICAL}
        for particao in dict.fromkeys(p["particao"] for p in perguntas):
            medida = medir_recuperacao(base, [p for p in perguntas if p["particao"] == particao])
            linha[particao] = {"acerto_top1": medida["acerto_top1"], "separacao_auc": medida["separacao_auc"]}
        linhas.append(linha)
    return linhas


# ------------------------------------------------------------------ 3. classificador de intenção

def avaliar_intencao(perguntas: List[Dict[str, Any]]) -> Dict[str, Any]:
    textos, rotulos = intencao.carregar_exemplos()
    classes = sorted(set(rotulos))
    dobras = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # Classificador em uso: regressão logística sobre embeddings.
    previstos = cross_val_predict(intencao.criar_classificador(), intencao.vetorizar(textos, usar_cache=True), rotulos, cv=dobras)

    # Classificador original (antes do ajuste): TF-IDF de n-gramas de caracteres.
    original = make_pipeline(
        TfidfVectorizer(preprocessor=normalizar, analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True),
        LogisticRegression(C=10, class_weight="balanced", max_iter=1000),
    )
    previstos_original = cross_val_predict(original, textos, rotulos, cv=dobras)

    mapa = {**{t: "relatorio" for t in TIPOS_NO_ESCOPO}, "fora_escopo": "fora_escopo",
            "conselho_medico": "conselho_medico", "saudacao": "saudacao"}
    externos = [p for p in perguntas if p["tipo"] in mapa]
    esperados = [mapa[p["tipo"]] for p in externos]
    obtidos = intencao.obter_classificador().predict(intencao.vetorizar([p["pergunta"] for p in externos])).tolist()

    injecoes = [p for p in perguntas if p["tipo"] == "injecao"]
    demais = [p for p in perguntas if p["tipo"] != "injecao"]
    conselhos = [p for p in perguntas if p["tipo"] == "conselho_medico"]
    sem_conselho = [p for p in perguntas if p["tipo"] not in ("conselho_medico", "injecao")]

    return {
        "exemplos_de_treino": len(textos),
        "validacao_cruzada": {
            "acuracia": round(accuracy_score(rotulos, previstos), 3),
            "f1_macro": round(f1_score(rotulos, previstos, average="macro"), 3),
            "classes": classes,
            "matriz_confusao": confusion_matrix(rotulos, previstos, labels=classes).tolist(),
        },
        "validacao_cruzada_classificador_original": {
            "descricao": "TF-IDF de n-gramas de caracteres + regressão logística",
            "acuracia": round(accuracy_score(rotulos, previstos_original), 3),
            "f1_macro": round(f1_score(rotulos, previstos_original, average="macro"), 3),
        },
        "regras_de_conselho_medico": {
            "detectadas": sum(intencao.detectar_conselho_medico(p["pergunta"]) for p in conselhos),
            "total": len(conselhos),
            "nao_detectadas": [p["pergunta"] for p in conselhos if not intencao.detectar_conselho_medico(p["pergunta"])],
            "falsos_alarmes": [p["pergunta"] for p in sem_conselho if intencao.detectar_conselho_medico(p["pergunta"])],
        },
        "conjunto_avaliacao": {
            "perguntas": len(externos),
            "acuracia": round(accuracy_score(esperados, obtidos), 3),
            "f1_macro": round(f1_score(esperados, obtidos, average="macro"), 3),
            "classes": classes,
            "matriz_confusao": confusion_matrix(esperados, obtidos, labels=classes).tolist(),
            "erros": [
                {"pergunta": p["pergunta"], "esperado": e, "obtido": o}
                for p, e, o in zip(externos, esperados, obtidos) if e != o
            ],
        },
        "regras_de_injecao": {
            "detectadas": sum(intencao.detectar_injecao(p["pergunta"]) for p in injecoes),
            "total": len(injecoes),
            "falsos_alarmes": [p["pergunta"] for p in demais if intencao.detectar_injecao(p["pergunta"])],
        },
    }


# ------------------------------------------------------------------ 4. validador

def avaliar_validador() -> Dict[str, Any]:
    with open(DIR / "casos_validador.json", "r", encoding="utf-8") as arquivo:
        casos = json.load(arquivo)["casos"]
    base = preparar_base_vetorial()

    def executar(caso: Dict[str, Any]) -> Dict[str, Any]:
        trechos = [Trecho(base.chunks[i], 1.0, 1.0, 0.0) for i in caso["fontes"]]
        return validador.validar_resposta(caso["resposta"], trechos, caso["nivel"], caso["pergunta"])

    linhas = []
    for caso in casos:
        validacao = executar(caso)
        decisao = "aprovar" if validacao["aprovada"] else "reprovar"
        linhas.append({
            "id": caso["id"], "esperado": caso["esperado"], "obtido": decisao,
            "correto": decisao == caso["esperado"], "defeito": caso.get("defeito"),
            "falhas": [c["nome"] for c in validacao["checagens"] if c["bloqueante"] and not c["ok"]],
            "apoio_minimo": min((f["apoio"] for f in validacao["frases"]), default=None),
        })

    ruins = [linha for linha in linhas if linha["esperado"] == "reprovar"]
    boas = [linha for linha in linhas if linha["esperado"] == "aprovar"]

    # Sensibilidade ao limiar de apoio por frase.
    original = validador.LIMIAR_FRASE
    curva = []
    for limiar in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75):
        validador.LIMIAR_FRASE = limiar
        aprovadas = [executar(caso)["aprovada"] for caso in casos]
        curva.append({
            "limiar": limiar,
            "defeitos_detectados": sum(1 for c, a in zip(casos, aprovadas) if c["esperado"] == "reprovar" and not a),
            "falsas_reprovacoes": sum(1 for c, a in zip(casos, aprovadas) if c["esperado"] == "aprovar" and not a),
        })
    validador.LIMIAR_FRASE = original

    return {
        "casos": len(linhas),
        "limiar_em_uso": original,
        "defeitos_detectados": sum(linha["correto"] for linha in ruins),
        "total_com_defeito": len(ruins),
        "falsas_reprovacoes": sum(not linha["correto"] for linha in boas),
        "total_corretas": len(boas),
        "curva_limiar": curva,
        "detalhe": linhas,
    }


# ------------------------------------------------------------------ 5. ponta a ponta

def avaliar_pipeline(perguntas: List[Dict[str, Any]], pausa: float) -> Dict[str, Any]:
    linhas = []
    for p in perguntas:
        resultado = agentes.responder(p["pergunta"], "simples", sessao="avaliacao", registrar=False)
        respondida = resultado["status"] == agentes.STATUS_RESPONDIDA
        usadas = [f["id"] for f in resultado["fontes"] if f["usada_no_contexto"]]
        aceitas = {p["fonte"], *p.get("fontes_aceitas", [])}
        texto = normalizar(resultado["resposta"])
        flesch = next((c["valor"] for c in resultado["validacao"]["checagens"] if c["nome"] == "legibilidade"), None)
        apoio = [f["apoio"] for f in resultado["validacao"]["frases"]]
        linhas.append({
            "id": p["id"], "tipo": p["tipo"], "particao": p["particao"], "pergunta": p["pergunta"],
            "status": resultado["status"], "status_correto": resultado["status"] in p["status"],
            "modo": resultado["modelo"]["modo"], "latencia_ms": resultado["latencia_ms"],
            "fonte_correta": bool(aceitas & set(usadas)) if respondida and p["fonte"] else None,
            "fatos_presentes": all(normalizar(f) in texto for f in p.get("fatos", [])) if respondida and p.get("fatos") else None,
            "aprovada": resultado["validacao"]["aprovada"] if respondida else None,
            "reprovadas_antes": len(resultado["validacao"]["tentativas_reprovadas"]),
            "uso_fallback": resultado["uso_fallback"],
            "flesch": flesch if respondida else None,
            "apoio_medio": media(apoio) if respondida and apoio else None,
            "resposta": resultado["resposta"],
        })
        if resultado["modelo"]["modo"] == "llm" and pausa:
            time.sleep(pausa)

    def taxa(campo: str, subconjunto: List[Dict[str, Any]]) -> Any:
        valores = [linha[campo] for linha in subconjunto if linha[campo] is not None]
        return media([int(v) for v in valores]) if valores else None

    respondidas = [linha for linha in linhas if linha["status"] == agentes.STATUS_RESPONDIDA]
    sensiveis = [linha for linha in linhas if linha["tipo"] in ("conselho_medico", "injecao")]
    latencias = sorted(linha["latencia_ms"] for linha in linhas)

    return {
        "perguntas": len(linhas),
        "acuracia_status": taxa("status_correto", linhas),
        "acuracia_por_particao": {
            particao: taxa("status_correto", [l for l in linhas if l["particao"] == particao])
            for particao in dict.fromkeys(l["particao"] for l in linhas)
        },
        "acuracia_por_tipo": {
            tipo: taxa("status_correto", [l for l in linhas if l["tipo"] == tipo])
            for tipo in dict.fromkeys(l["tipo"] for l in linhas)
        },
        "vazamentos": [l["pergunta"] for l in sensiveis if l["status"] == agentes.STATUS_RESPONDIDA],
        "falsas_recusas": [l["pergunta"] for l in linhas if l["tipo"] in TIPOS_NO_ESCOPO and not l["status_correto"]],
        "respostas_indevidas": [l["pergunta"] for l in linhas if l["tipo"] in TIPOS_SEM_COBERTURA and not l["status_correto"]],
        "respondidas": {
            "total": len(respondidas),
            "fonte_correta": taxa("fonte_correta", respondidas),
            "fatos_presentes": taxa("fatos_presentes", respondidas),
            "aprovadas_pelo_auditor": taxa("aprovada", respondidas),
            "reprovadas_na_primeira_versao": sum(1 for l in respondidas if l["reprovadas_antes"]),
            "uso_fallback": sum(1 for l in respondidas if l["uso_fallback"]),
            "apoio_medio": media([l["apoio_medio"] for l in respondidas if l["apoio_medio"] is not None]),
            "flesch_medio": round(statistics.mean(l["flesch"] for l in respondidas if l["flesch"] is not None), 1) if respondidas else None,
        },
        "latencia_ms": {
            "p50": latencias[len(latencias) // 2],
            "p95": latencias[min(len(latencias) - 1, int(0.95 * len(latencias)))],
        },
        "detalhe": linhas,
    }


# ------------------------------------------------------------------ 6. consistência

def similaridade_media(textos: List[str]) -> float:
    """Média da similaridade de cosseno entre todos os pares de textos (1,0 = idênticos em sentido)."""
    if len(textos) < 2:
        return 1.0
    vetores = np.array(gerar_embeddings(textos))
    vetores /= np.linalg.norm(vetores, axis=1, keepdims=True)
    pares = list(itertools.combinations(range(len(textos)), 2))
    return round(float(np.mean([vetores[a] @ vetores[b] for a, b in pares])), 3)


def avaliar_consistencia(perguntas: List[Dict[str, Any]], pipeline: Dict[str, Any],
                         repeticoes: int, pausa: float) -> Dict[str, Any]:
    diretas = [p for p in perguntas if p["tipo"] == "direta"][:8]
    repeticao = []
    for p in diretas:
        respostas, fontes = [], []
        for _ in range(repeticoes):
            resultado = agentes.responder(p["pergunta"], "simples", sessao="avaliacao", registrar=False)
            respostas.append(resultado["resposta"])
            fontes.append(tuple(f["id"] for f in resultado["fontes"] if f["usada_no_contexto"]))
            if resultado["modelo"]["modo"] == "llm" and pausa:
                time.sleep(pausa)
        repeticao.append({
            "pergunta": p["pergunta"],
            "similaridade": similaridade_media(respostas),
            "respostas_distintas": len(set(respostas)),
            "mesmas_fontes": len(set(fontes)) == 1,
        })

    # Paráfrases: perguntas diferentes sobre o mesmo tema devem levar a respostas equivalentes.
    por_fonte: Dict[str, List[str]] = {}
    for linha in pipeline["detalhe"]:
        pergunta = next(p for p in perguntas if p["id"] == linha["id"])
        if linha["status"] == agentes.STATUS_RESPONDIDA and pergunta["fonte"]:
            por_fonte.setdefault(pergunta["fonte"], []).append(linha["resposta"])
    parafrases = [
        {"tema": fonte, "formulacoes": len(respostas), "similaridade": similaridade_media(respostas)}
        for fonte, respostas in por_fonte.items() if len(respostas) >= 2
    ]

    return {
        "repeticoes_por_pergunta": repeticoes,
        "temperatura": llm.config_atual().temperatura if llm.config_atual().ativo else None,
        "repeticao": {
            "similaridade_media": media([r["similaridade"] for r in repeticao]),
            "similaridade_minima": min(r["similaridade"] for r in repeticao),
            "perguntas_com_resposta_identica": sum(1 for r in repeticao if r["respostas_distintas"] == 1),
            "perguntas_com_mesmas_fontes": sum(1 for r in repeticao if r["mesmas_fontes"]),
            "total": len(repeticao),
            "detalhe": repeticao,
        },
        "parafrases": {
            "similaridade_media": media([p["similaridade"] for p in parafrases]),
            "detalhe": parafrases,
        },
    }


# ------------------------------------------------------------------ critérios e execução

def verificar_criterios(resultado: Dict[str, Any]) -> List[Dict[str, Any]]:
    final = resultado["recuperacao"][-1]
    v = resultado["validador"]
    medidos = [
        ("recuperacao_acerto_top3", final["acerto_top3"], final["acerto_top3"] >= CRITERIOS["recuperacao_acerto_top3"]),
        ("pipeline_acuracia_status", resultado["pipeline"]["acuracia_status"],
         resultado["pipeline"]["acuracia_status"] >= CRITERIOS["pipeline_acuracia_status"]),
        ("pipeline_vazamentos", len(resultado["pipeline"]["vazamentos"]),
         len(resultado["pipeline"]["vazamentos"]) <= CRITERIOS["pipeline_vazamentos"]),
        ("validador_defeitos_detectados", round(v["defeitos_detectados"] / v["total_com_defeito"], 3),
         v["defeitos_detectados"] / v["total_com_defeito"] >= CRITERIOS["validador_defeitos_detectados"]),
        ("validador_falsas_reprovacoes_max", v["falsas_reprovacoes"],
         v["falsas_reprovacoes"] <= CRITERIOS["validador_falsas_reprovacoes_max"]),
    ]
    return [{"criterio": nome, "minimo": CRITERIOS[nome], "obtido": obtido, "ok": bool(ok)} for nome, obtido, ok in medidos]


def main() -> int:
    parser = argparse.ArgumentParser(description="Avaliação do GenIA")
    parser.add_argument("--rapido", action="store_true", help="avalia só a configuração final de recuperação")
    parser.add_argument("--repeticoes", type=int, default=5, help="repetições por pergunta no teste de consistência")
    parser.add_argument("--pausa", type=float, default=0.0, help="segundos entre chamadas ao LLM")
    parser.add_argument("--sem-relatorio", action="store_true", help="não regenera docs/avaliacao.md")
    argumentos = parser.parse_args()

    configuracao = llm.config_atual()
    modo = f"{configuracao.provedor}-{configuracao.modelo}".replace("/", "-").replace(":", "-") if configuracao.ativo else "extrativo"
    perguntas = carregar_perguntas()
    print(f"Avaliando no modo '{modo}' com {len(perguntas)} perguntas")

    resultado: Dict[str, Any] = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modo": modo,
        "configuracao": {
            "provedor": configuracao.provedor, "modelo": configuracao.modelo,
            "temperatura": configuracao.temperatura if configuracao.ativo else None,
            "prompt_versao": prompts.PROMPT_VERSAO, "embedding": config.MODELO_EMBEDDING,
            "top_k": config.TOP_K, "score_minimo": config.SCORE_MINIMO, "peso_lexical": config.PESO_LEXICAL,
            "limiar_frase": validador.LIMIAR_FRASE,
        },
        "perguntas": len(perguntas),
    }

    print("1/6 recuperação")
    resultado["recuperacao"] = avaliar_recuperacao(perguntas, argumentos.rapido)
    print("2/6 limiar de escopo")
    resultado["limiar"] = calibrar_limiar(perguntas)
    if not argumentos.rapido:
        resultado["peso_lexical"] = avaliar_peso_lexical(perguntas)
    print("3/6 classificador de intenção")
    resultado["intencao"] = avaliar_intencao(perguntas)
    print("4/6 validador")
    resultado["validador"] = avaliar_validador()
    print("5/6 ponta a ponta")
    resultado["pipeline"] = avaliar_pipeline(perguntas, argumentos.pausa)
    print("6/6 consistência")
    resultado["consistencia"] = avaliar_consistencia(perguntas, resultado["pipeline"], argumentos.repeticoes, argumentos.pausa)
    resultado["criterios"] = verificar_criterios(resultado)

    DIR_RESULTADOS.mkdir(exist_ok=True)
    destino = DIR_RESULTADOS / f"{modo}.json"
    if argumentos.rapido and destino.exists():
        # A execução rápida não refaz a comparação entre configurações: preserva a que já existe.
        anterior = json.loads(destino.read_text(encoding="utf-8"))
        if len(anterior.get("recuperacao", [])) > 1:
            resultado["recuperacao"] = anterior["recuperacao"][:-1] + resultado["recuperacao"][-1:]
        if "peso_lexical" in anterior:
            resultado["peso_lexical"] = anterior["peso_lexical"]
    # default=: converte os tipos numéricos do numpy, que o json não serializa.
    destino.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, default=lambda valor: valor.item()),
        encoding="utf-8",
    )
    print(f"\nResultado gravado em {destino.relative_to(config.RAIZ)}")

    if not argumentos.sem_relatorio:
        from avaliacao.gerar_relatorio import gerar
        print(f"Relatório regenerado em {gerar().relative_to(config.RAIZ)}")

    print("\nCritérios mínimos:")
    for c in resultado["criterios"]:
        print(f"  [{'OK' if c['ok'] else 'FALHOU'}] {c['criterio']}: {c['obtido']} (mínimo {c['minimo']})")
    return 0 if all(c["ok"] for c in resultado["criterios"]) else 1


if __name__ == "__main__":
    sys.exit(main())
