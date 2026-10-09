"""
Orquestração multiagente do GenIA.

Cada pergunta percorre quatro agentes com papéis separados:

1. Triagem     — mascara dados pessoais e classifica a intenção (scikit-learn + regras).
2. Recuperador — busca os trechos do relatório (busca híbrida) e decide se há cobertura.
3. Redator     — escreve a resposta com o LLM, restrito aos trechos recuperados.
4. Auditor     — valida a resposta; reprova, pede reescrita e, se preciso, troca pela
                 resposta extrativa (feita só com frases do relatório).

Cada agente registra o que decidiu e por quê. Esse rastro é devolvido junto com a
resposta (explicabilidade) e gravado no log de auditoria.
"""
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from app import auditoria, intencao, llm, prompts, validador
from app.config import LIMITE_LLM_DIA, MODELO_EMBEDDING, SCORE_MINIMO, SEMANTICO_SEM_ANCORA, TOP_K
from app.privacidade import mascarar_pii, pseudonimizar
from app.rag import Trecho, preparar_base_vetorial

STATUS_RESPONDIDA = "respondida"
STATUS_SEM_INFORMACAO = "sem_informacao"
STATUS_FORA_ESCOPO = "recusada_fora_escopo"
STATUS_CONSELHO = "recusada_conselho_medico"
STATUS_BLOQUEADA = "bloqueada"
STATUS_SAUDACAO = "saudacao"
STATUS_RETIDA = "retida_pelo_auditor"

# Confiança mínima do classificador para a triagem agir sozinha. O pedido de conselho médico
# é decidido sobretudo por regra; o classificador só recusa sozinho quando está muito seguro,
# porque perguntas leigas legítimas ("leite me faz mal?") se parecem com pedidos de conselho.
CONFIANCA_SAUDACAO = 0.6
CONFIANCA_CONSELHO = 0.9
# Um trecho só entra no contexto do Redator se pontuar ao menos esta fração do melhor trecho.
FRACAO_DO_MELHOR = 0.6

_resumos: Dict[tuple, Dict[str, Any]] = {}


class Rastro:
    """Acumula as etapas executadas pelos agentes em uma interação."""

    def __init__(self) -> None:
        self.etapas: List[Dict[str, Any]] = []

    def executar(self, agente: str, funcao: Callable[[], Any], descrever: Callable[[Any], Dict[str, Any]]) -> Any:
        inicio = time.perf_counter()
        resultado = funcao()
        descricao = descrever(resultado)
        self.etapas.append({
            "agente": agente,
            "duracao_ms": round((time.perf_counter() - inicio) * 1000),
            "decisao": descricao.pop("decisao"),
            "detalhes": descricao,
        })
        return resultado


NOMES_INTENCAO = {
    intencao.INTENCAO_RELATORIO: "pergunta sobre o relatório",
    intencao.INTENCAO_CONSELHO: "pedido de conselho médico",
    intencao.INTENCAO_FORA: "assunto fora do relatório",
    intencao.INTENCAO_SAUDACAO: "saudação",
    intencao.INTENCAO_INJECAO: "tentativa de injeção de instruções",
}


def intencao_efetiva(classe: intencao.Intencao) -> str:
    """
    Intenção que a Triagem de fato adota. Regras valem sempre; o classificador só decide
    sozinho (saudação, conselho médico) acima da confiança mínima. Nos demais casos a pergunta
    segue como pergunta sobre o relatório, e é o Recuperador que decide se há cobertura.
    """
    if classe.origem == "regra":
        return classe.rotulo
    if classe.rotulo == intencao.INTENCAO_SAUDACAO and classe.confianca >= CONFIANCA_SAUDACAO:
        return classe.rotulo
    if classe.rotulo == intencao.INTENCAO_CONSELHO and classe.confianca >= CONFIANCA_CONSELHO:
        return classe.rotulo
    return intencao.INTENCAO_RELATORIO


def avaliar_cobertura(trechos: Sequence[Trecho]) -> Tuple[bool, str]:
    """
    Decide se o relatório cobre a pergunta. Duas condições:

    1. o melhor trecho atinge a pontuação mínima; e
    2. há uma âncora lexical (alguma palavra relevante da pergunta aparece no trecho ou no
       glossário) — ou, na falta dela, a similaridade semântica é alta.

    A segunda condição existe porque perguntas sobre temas de saúde ausentes do relatório
    ("qual é meu colesterol?") ficam semanticamente próximas de temas presentes e passavam
    só pelo limiar — ver docs/avaliacao.md.
    """
    if not trechos:
        return False, "nenhum trecho recuperado"
    melhor = trechos[0]
    if melhor.score < SCORE_MINIMO:
        return False, f"pontuação {melhor.score:.2f} abaixo do mínimo de {SCORE_MINIMO:.2f}"
    if melhor.score_lexical <= 0 and melhor.score_semantico < SEMANTICO_SEM_ANCORA:
        return False, (
            f"nenhuma palavra da pergunta aparece no trecho mais próximo e a similaridade semântica "
            f"({melhor.score_semantico:.2f}) é inferior a {SEMANTICO_SEM_ANCORA:.2f}"
        )
    return True, f"pontuação {melhor.score:.2f} (mínimo {SCORE_MINIMO:.2f})"


# ---------------------------------------------------------------- respostas extrativas

def _percentual(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",") + "%"


def resposta_extrativa(trechos: Sequence[Trecho], nivel: str = "simples") -> str:
    """
    Resposta montada apenas com frases do trecho mais relevante, sem LLM.
    É o modo de operação sem provedor configurado e a rede de segurança do Auditor.
    """
    chunk = trechos[0].chunk
    campos = chunk.campos

    if chunk.id == "ancestralidade:visao-geral":
        composicao = "; ".join(f"{i['origem']} {_percentual(i['percentual'])}" for i in campos["composicao"])
        texto = f"{campos['resumo']} Composição: {composicao}."
    elif chunk.id.startswith("ancestralidade:"):
        texto = (
            f"O relatório indica {_percentual(campos['percentual'])} de ancestralidade "
            f"{campos['origem'].lower()}. {campos['explicacao']}"
        )
    elif chunk.id.startswith("avisos:"):
        texto = " ".join(campos["avisos"])
    else:
        explicacao = campos["explicacao_simples"] if nivel == "simples" else campos["explicacao_tecnica"]
        risco = f" Nível de risco: {campos['nivel_risco']}." if campos.get("nivel_risco") else ""
        texto = f"{chunk.tema}: {campos['resultado']}.{risco} {explicacao} {campos['recomendacao']}"

    return f"{texto} [{chunk.id}]"


def resumo_extrativo(chunks: Sequence, nivel: str = "simples") -> str:
    por_id = {chunk.id: chunk for chunk in chunks}
    paragrafos = []

    geral = por_id.get("ancestralidade:visao-geral")
    if geral:
        composicao = "; ".join(f"{i['origem']} {_percentual(i['percentual'])}" for i in geral.campos["composicao"])
        paragrafos.append(f"{geral.campos['resumo']} Composição: {composicao}. [{geral.id}]")

    for prefixo in ("saude:", "bem-estar:"):
        frases = []
        for chunk in chunks:
            if chunk.id.startswith(prefixo):
                explicacao = chunk.campos["explicacao_simples" if nivel == "simples" else "explicacao_tecnica"]
                frases.append(f"{chunk.tema}: {chunk.campos['resultado']}. {explicacao} [{chunk.id}]")
        if frases:
            paragrafos.append(" ".join(frases))

    return "\n\n".join(paragrafos)


# ---------------------------------------------------------------- redator + auditor

def _redigir_e_auditar(rastro: Rastro, mensagens: List[Dict[str, str]], trechos: Sequence[Trecho],
                       nivel: str, pergunta: str, extrativa: Callable[[], str],
                       resumo: bool = False) -> Dict[str, Any]:
    """
    Redator escreve, Auditor valida. Se a resposta do LLM for reprovada, o Redator recebe os
    motivos e reescreve uma vez; se reprovar de novo (ou o LLM falhar), entra a resposta extrativa.
    """
    config = llm.config_atual()
    reprovadas: List[Dict[str, Any]] = []
    erro_llm: Optional[str] = None

    def auditar(texto: str) -> Dict[str, Any]:
        return rastro.executar(
            "Auditor",
            lambda: validador.validar_resposta(texto, trechos, nivel, pergunta, resumo=resumo),
            lambda v: {
                "decisao": "aprovada" if v["aprovada"] else "reprovada",
                "falhas": validador.motivos_reprovacao(v),
            },
        )

    # Teto diário de uso do LLM: protege o custo da chave quando a aplicação está pública.
    # Atingido o teto, as respostas passam a ser extrativas até o dia seguinte.
    if config.ativo and auditoria.geracoes_llm_hoje() >= LIMITE_LLM_DIA > 0:
        erro_llm = f"teto diário de {LIMITE_LLM_DIA} gerações com LLM atingido"
        rastro.etapas.append({
            "agente": "Redator", "duracao_ms": 0,
            "decisao": "teto diário do LLM atingido; usando resposta extrativa",
            "detalhes": {"teto": LIMITE_LLM_DIA},
        })
    elif config.ativo:
        conversa = list(mensagens)
        for tentativa in (1, 2):
            try:
                texto = rastro.executar(
                    "Redator",
                    lambda: validador.normalizar_citacoes(llm.gerar(conversa, config)),
                    lambda t: {"decisao": f"resposta gerada pelo LLM (tentativa {tentativa})",
                               "modelo": config.modelo, "prompt_versao": prompts.PROMPT_VERSAO},
                )
            except llm.ErroLLM as erro:
                erro_llm = str(erro)
                rastro.etapas.append({
                    "agente": "Redator", "duracao_ms": 0,
                    "decisao": "falha no LLM; usando resposta extrativa",
                    "detalhes": {"erro": erro_llm},
                })
                break

            if validador.FRASE_SEM_INFORMACAO.rstrip(".").lower() in texto.lower():
                return {"texto": validador.FRASE_SEM_INFORMACAO, "validacao": None, "modo": "llm",
                        "sem_informacao": True, "reprovadas": reprovadas, "erro_llm": None, "config": config}

            validacao = auditar(texto)
            if validacao["aprovada"]:
                return {"texto": texto, "validacao": validacao, "modo": "llm", "sem_informacao": False,
                        "reprovadas": reprovadas, "erro_llm": None, "config": config}

            motivos = validador.motivos_reprovacao(validacao)
            reprovadas.append({"tentativa": tentativa, "motivos": motivos})
            conversa = conversa + [
                {"role": "assistant", "content": texto},
                {"role": "user", "content": prompts.CORRECAO_AUDITOR.format(motivos="\n".join(f"- {m}" for m in motivos))},
            ]

    texto = rastro.executar(
        "Redator", extrativa,
        lambda t: {"decisao": "resposta extrativa (somente frases do relatório)",
                   "motivo": "sem LLM configurado" if not config.ativo else (erro_llm or "LLM reprovado na auditoria")},
    )
    return {"texto": texto, "validacao": auditar(texto), "modo": "extrativo", "sem_informacao": False,
            "reprovadas": reprovadas, "erro_llm": erro_llm, "config": config}


def _fonte(trecho: Trecho, usada: bool) -> Dict[str, Any]:
    return {
        "id": trecho.chunk.id,
        "secao": trecho.chunk.secao,
        "tema": trecho.chunk.tema,
        "texto": trecho.chunk.texto,
        "score": trecho.score,
        "score_semantico": trecho.score_semantico,
        "score_lexical": trecho.score_lexical,
        "usada_no_contexto": usada,
    }


def _explicar(status: str, classe: Optional[intencao.Intencao], fontes: List[Dict[str, Any]],
              redacao: Optional[Dict[str, Any]], motivo_cobertura: str = "") -> str:
    """Explicação em linguagem natural de como a resposta foi produzida."""
    partes = []
    if classe:
        efetiva = intencao_efetiva(classe)
        if classe.origem == "regra":
            partes.append(f"Uma regra de segurança identificou a pergunta como {NOMES_INTENCAO[efetiva]}.")
        elif efetiva == classe.rotulo:
            partes.append(
                f"O classificador de intenção identificou a pergunta como {NOMES_INTENCAO[efetiva]} "
                f"(confiança {classe.confianca:.0%})."
            )
        else:
            partes.append(
                f"A pergunta foi tratada como {NOMES_INTENCAO[efetiva]}: o classificador sugeriu "
                f"{NOMES_INTENCAO[classe.rotulo]} com confiança de {classe.confianca:.0%}, insuficiente para "
                "recusar sem consultar o relatório."
            )

    if status == STATUS_BLOQUEADA:
        partes.append("Ela não foi enviada ao modelo de linguagem.")
    elif status == STATUS_SAUDACAO:
        partes.append("Por não ser uma pergunta sobre o relatório, a resposta é uma mensagem fixa.")
    elif status == STATUS_CONSELHO:
        partes.append("Pedidos de diagnóstico, medicamento ou tratamento recebem uma recusa fixa, sem uso do modelo de linguagem.")
    elif status == STATUS_FORA_ESCOPO:
        partes.append(f"O sistema não respondeu porque o relatório não cobre a pergunta: {motivo_cobertura}.")
    elif status == STATUS_RETIDA:
        partes.append("Nenhuma versão da resposta passou em todas as checagens do Auditor, então ela foi retida.")
    elif redacao:
        usadas = [f for f in fontes if f["usada_no_contexto"]]
        partes.append(
            "A busca encontrou " + ", ".join(f"\"{f['tema']}\" ({f['score']:.2f})" for f in usadas)
            + " como os trechos mais relevantes do relatório."
        )
        if status == STATUS_SEM_INFORMACAO:
            partes.append("O modelo de linguagem concluiu que esses trechos não tratam do tema perguntado.")
        elif redacao["modo"] == "llm":
            partes.append(
                f"A resposta foi escrita pelo modelo {redacao['config'].modelo} usando apenas esses trechos "
                f"(prompt {prompts.PROMPT_VERSAO}) e aprovada pelo Auditor."
            )
        else:
            partes.append("A resposta foi montada apenas com frases do próprio relatório, sem geração de texto.")
        if redacao["reprovadas"]:
            partes.append(f"O Auditor reprovou {len(redacao['reprovadas'])} versão(ões) antes desta.")
    return " ".join(partes)


# ---------------------------------------------------------------- pontos de entrada

def responder(pergunta: str, nivel: str = "simples", sessao: str = "anonima",
              guardar_conteudo: bool = False, registrar: bool = True) -> Dict[str, Any]:
    """Responde a uma pergunta sobre o relatório, passando pelos quatro agentes."""
    inicio = time.perf_counter()
    trace_id = uuid.uuid4().hex
    nivel = nivel if nivel in prompts.NIVEIS else "simples"
    rastro = Rastro()
    base = preparar_base_vetorial()

    # 1. Triagem
    pergunta_mascarada, pii = mascarar_pii(pergunta.strip())
    classe = rastro.executar(
        "Triagem",
        lambda: intencao.classificar(pergunta_mascarada),
        lambda c: {"decisao": f"tratada como: {NOMES_INTENCAO[intencao_efetiva(c)]}",
                   "sugestao_do_classificador": c.rotulo, "confianca": c.confianca,
                   "origem": c.origem, "dados_pessoais_mascarados": pii},
    )
    efetiva = intencao_efetiva(classe)

    status = STATUS_RESPONDIDA
    resposta = ""
    trechos: List[Trecho] = []
    contexto: List[Trecho] = []
    redacao: Optional[Dict[str, Any]] = None
    motivo_cobertura = ""

    if efetiva == intencao.INTENCAO_INJECAO:
        status, resposta = STATUS_BLOQUEADA, prompts.BLOQUEIO_INJECAO
    elif efetiva == intencao.INTENCAO_SAUDACAO:
        status, resposta = STATUS_SAUDACAO, prompts.SAUDACAO
    else:
        # 2. Recuperador
        trechos = rastro.executar(
            "Recuperador",
            lambda: base.buscar(pergunta_mascarada, TOP_K),
            lambda ts: {
                "decisao": "relatório cobre a pergunta" if avaliar_cobertura(ts)[0] else "relatório não cobre a pergunta",
                "motivo": avaliar_cobertura(ts)[1],
                "trechos": [{"id": t.chunk.id, "score": t.score} for t in ts],
            },
        )
        coberta, motivo_cobertura = avaliar_cobertura(trechos)

        if efetiva == intencao.INTENCAO_CONSELHO:
            status, resposta = STATUS_CONSELHO, prompts.RECUSA_CONSELHO_MEDICO
            if coberta:
                resposta += f" Se quiser, posso explicar o que o seu relatório diz sobre {trechos[0].chunk.tema.lower()}."
        elif not coberta:
            status, resposta = STATUS_FORA_ESCOPO, prompts.RECUSA_FORA_ESCOPO
        else:
            contexto = [t for t in trechos if t.score >= max(SCORE_MINIMO, trechos[0].score * FRACAO_DO_MELHOR)]

            # 3 e 4. Redator e Auditor
            redacao = _redigir_e_auditar(
                rastro, prompts.montar_mensagens(pergunta_mascarada, contexto, nivel), contexto, nivel,
                pergunta_mascarada, lambda: resposta_extrativa(contexto, nivel),
            )
            resposta = redacao["texto"]
            if redacao["sem_informacao"]:
                status = STATUS_SEM_INFORMACAO
            elif not redacao["validacao"]["aprovada"]:
                # Nem a resposta extrativa passou: nada é exibido além de uma mensagem fixa.
                status, resposta = STATUS_RETIDA, prompts.RESPOSTA_RETIDA

    ids_contexto = {t.chunk.id for t in contexto}
    fontes = [_fonte(t, t.chunk.id in ids_contexto) for t in trechos]
    config = redacao["config"] if redacao else llm.config_atual()
    modo = redacao["modo"] if redacao else "mensagem_fixa"
    validacao = (redacao or {}).get("validacao") or {"aprovada": True, "checagens": [], "frases": []}
    validacao["tentativas_reprovadas"] = (redacao or {}).get("reprovadas", [])
    uso_fallback = bool(redacao and config.ativo and redacao["modo"] == "extrativo")
    latencia_ms = round((time.perf_counter() - inicio) * 1000)

    resultado = {
        "trace_id": trace_id,
        "pergunta": pergunta_mascarada,
        "resposta": resposta,
        "aviso": prompts.AVISO_PADRAO,
        "nivel": nivel,
        "status": status,
        "intencao": {"rotulo": efetiva, "sugestao_do_classificador": classe.rotulo,
                     "confianca": classe.confianca, "origem": classe.origem},
        "fontes": fontes,
        "validacao": validacao,
        "etapas": rastro.etapas,
        "explicacao": _explicar(status, classe, fontes, redacao, motivo_cobertura),
        "modelo": {
            "modo": modo,
            "provedor": config.provedor if modo == "llm" else modo,
            "modelo": config.modelo if modo == "llm" else None,
            "temperatura": config.temperatura if modo == "llm" else None,
            "prompt_versao": prompts.PROMPT_VERSAO,
            "embedding": MODELO_EMBEDDING,
            "base_versao": base.versao,
        },
        "uso_fallback": uso_fallback,
        "pii_mascarada": pii,
        "latencia_ms": latencia_ms,
    }

    if registrar:
        auditoria.registrar_interacao({
            "trace_id": trace_id, "sessao": pseudonimizar(sessao), "tipo": "pergunta",
            "pergunta": pergunta_mascarada, "resposta": resposta, "conteudo_gravado": guardar_conteudo,
            "nivel": nivel, "intencao": efetiva, "status": status,
            "fontes": [{"id": f["id"], "score": f["score"], "usada_no_contexto": f["usada_no_contexto"]} for f in fontes],
            "validacao": {
                "aprovada": validacao["aprovada"],
                "checagens": [{k: c[k] for k in ("nome", "ok", "valor")} for c in validacao["checagens"]],
                "tentativas_reprovadas": validacao["tentativas_reprovadas"],
            },
            "etapas": [{k: e[k] for k in ("agente", "duracao_ms", "decisao")} for e in rastro.etapas],
            "pii_mascarada": pii,
            "provedor": resultado["modelo"]["provedor"], "modelo": resultado["modelo"]["modelo"],
            "prompt_versao": prompts.PROMPT_VERSAO, "embedding": MODELO_EMBEDDING, "base_versao": base.versao,
            "uso_fallback": uso_fallback, "latencia_ms": latencia_ms,
        })
        if uso_fallback:
            auditoria.registrar_evento("fallback_llm", {
                "trace_id": trace_id,
                "motivo": redacao["erro_llm"] or "resposta do LLM reprovada pelo Auditor",
            })

    return resultado


def resumir(nivel: str = "simples", sessao: str = "anonima", registrar: bool = True) -> Dict[str, Any]:
    """
    Resumo automático do relatório inteiro, com a mesma auditoria das respostas.
    O resumo é igual para todos os acessos ao mesmo relatório, então fica em cache por
    (nível, versão da base, modelo): economiza chamadas ao LLM.
    """
    inicio = time.perf_counter()
    nivel = nivel if nivel in prompts.NIVEIS else "simples"
    base = preparar_base_vetorial()
    config = llm.config_atual()
    chave = (nivel, base.versao, config.provedor, config.modelo, prompts.PROMPT_VERSAO)

    if chave in _resumos:
        return {**_resumos[chave], "em_cache": True}

    rastro = Rastro()
    chunks = [
        chunk for chunk in base.chunks.values()
        if not chunk.id.startswith("avisos:")
        and (not chunk.id.startswith("ancestralidade:") or chunk.id == "ancestralidade:visao-geral")
    ]
    trechos = [Trecho(chunk=chunk, score=1.0, score_semantico=1.0, score_lexical=0.0) for chunk in chunks]

    redacao = _redigir_e_auditar(
        rastro, prompts.montar_mensagens_resumo(trechos, nivel), trechos, nivel, "",
        lambda: resumo_extrativo(chunks, nivel), resumo=True,
    )
    if redacao["sem_informacao"]:
        redacao = {**redacao, "texto": resumo_extrativo(chunks, nivel), "modo": "extrativo", "validacao": None}

    validacao = redacao["validacao"] or validador.validar_resposta(redacao["texto"], trechos, nivel, resumo=True)
    validacao["tentativas_reprovadas"] = redacao["reprovadas"]
    modo = redacao["modo"]
    trace_id = uuid.uuid4().hex
    latencia_ms = round((time.perf_counter() - inicio) * 1000)

    resultado = {
        "trace_id": trace_id,
        "resumo": redacao["texto"],
        "aviso": prompts.AVISO_PADRAO,
        "nivel": nivel,
        "fontes": [{"id": chunk.id, "tema": chunk.tema, "secao": chunk.secao} for chunk in chunks],
        "validacao": validacao,
        "etapas": rastro.etapas,
        "modelo": {
            "modo": modo,
            "provedor": config.provedor if modo == "llm" else modo,
            "modelo": config.modelo if modo == "llm" else None,
            "prompt_versao": prompts.PROMPT_VERSAO,
            "base_versao": base.versao,
        },
        "latencia_ms": latencia_ms,
        "em_cache": False,
    }
    _resumos[chave] = resultado

    if registrar:
        auditoria.registrar_interacao({
            "trace_id": trace_id, "sessao": pseudonimizar(sessao), "tipo": "resumo",
            "conteudo_gravado": False, "nivel": nivel, "intencao": None, "status": STATUS_RESPONDIDA,
            "fontes": [{"id": chunk.id} for chunk in chunks],
            "validacao": {
                "aprovada": validacao["aprovada"],
                "checagens": [{k: c[k] for k in ("nome", "ok", "valor")} for c in validacao["checagens"]],
                "tentativas_reprovadas": validacao["tentativas_reprovadas"],
            },
            "etapas": [{k: e[k] for k in ("agente", "duracao_ms", "decisao")} for e in rastro.etapas],
            "provedor": resultado["modelo"]["provedor"], "modelo": resultado["modelo"]["modelo"],
            "prompt_versao": prompts.PROMPT_VERSAO, "embedding": MODELO_EMBEDDING, "base_versao": base.versao,
            "uso_fallback": bool(config.ativo and modo == "extrativo"), "latencia_ms": latencia_ms,
        })

    return resultado
