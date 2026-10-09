"""
API HTTP do GenIA (FastAPI). É o que o front-end consome.

Execução local: uvicorn app.api:app --reload
"""
import json
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any, Deque, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import agentes, auditoria, config, llm, pipeline, prompts
from app.data_loader import carregar_relatorio
from app.privacidade import VERSAO_TERMO, pseudonimizar
from app.rag import preparar_base_vetorial

CAMINHO_AVALIACAO = config.RAIZ / "avaliacao" / "resultados"

estado: Dict[str, Any] = {"iniciado_em": None, "ingestao": None}


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    # Na subida: aplica a política de retenção e executa o pipeline de ingestão monitorado.
    estado["iniciado_em"] = time.time()
    auditoria.aplicar_retencao()
    estado["ingestao"] = pipeline.executar_ingestao()
    yield


app = FastAPI(title="GenIA", version=config.VERSAO_APP, lifespan=ciclo_de_vida)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ORIGENS_PERMITIDAS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Sessao", "X-Token-Operador"],
)


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=1, max_length=500)
    nivel: str = Field(default="simples", pattern="^(simples|tecnico)$")


class Consentimento(BaseModel):
    guardar_conteudo: bool = False


class Feedback(BaseModel):
    trace_id: str = Field(min_length=8, max_length=64)
    util: bool


def sessao_da(requisicao: Request) -> str:
    """Identificador de sessão enviado pelo front-end. O que é gravado é sempre o pseudônimo."""
    sessao = requisicao.headers.get("X-Sessao", "").strip()
    if not 8 <= len(sessao) <= 64:
        raise HTTPException(status_code=400, detail="Cabeçalho X-Sessao ausente ou inválido.")
    return sessao


_janelas: Dict[str, Deque[float]] = defaultdict(deque)


def limitar_uso(sessao: str) -> None:
    """Limite de requisições por sessão: protege a cota do provedor de LLM contra abuso."""
    agora, janela = time.time(), _janelas[sessao]
    while janela and agora - janela[0] > 60:
        janela.popleft()
    if len(janela) >= config.LIMITE_POR_MINUTO:
        raise HTTPException(status_code=429, detail="Muitas perguntas em pouco tempo. Aguarde um minuto.")
    janela.append(agora)


def exigir_operador(requisicao: Request) -> None:
    """Operações administrativas exigem o token de operador (variável GENIA_TOKEN_OPERADOR)."""
    if not config.TOKEN_OPERADOR:
        raise HTTPException(status_code=403, detail="Operação desabilitada: token de operador não configurado.")
    if not secrets.compare_digest(requisicao.headers.get("X-Token-Operador", ""), config.TOKEN_OPERADOR):
        raise HTTPException(status_code=403, detail="Token de operador inválido.")


def exigir_consentimento(sessao: str) -> Dict[str, Any]:
    consentimento = auditoria.obter_consentimento(pseudonimizar(sessao))
    if consentimento is None or consentimento["versao_termo"] != VERSAO_TERMO:
        raise HTTPException(status_code=403, detail="É preciso aceitar o termo de uso e privacidade antes de continuar.")
    return consentimento


@app.get("/api/saude")
def saude() -> Dict[str, Any]:
    """Verificação de saúde, usada pelo monitoramento agendado."""
    ingestao = estado["ingestao"] or {}
    modelo = llm.config_atual()
    pronto = ingestao.get("status") == "sucesso"
    return {
        "status": "ok" if pronto else "degradado",
        "versao": config.VERSAO_APP,
        "ativo_ha_segundos": round(time.time() - estado["iniciado_em"]) if estado["iniciado_em"] else 0,
        "ingestao": {"status": ingestao.get("status"), "erro": ingestao.get("erro"), "duracao_ms": ingestao.get("duracao_ms")},
        "base_versao": preparar_base_vetorial().versao if pronto else None,
        "llm": {"provedor": modelo.provedor, "modelo": modelo.modelo if modelo.ativo else None},
        "prompt_versao": prompts.PROMPT_VERSAO,
    }


@app.get("/api/relatorio")
def relatorio() -> Dict[str, Any]:
    """Dados do relatório para o painel. A identificação do paciente não é enviada."""
    dados = carregar_relatorio()
    return {
        "id_relatorio": dados.get("id_relatorio"),
        "tipo_relatorio": dados.get("tipo_relatorio"),
        "data_emissao": dados.get("paciente", {}).get("data_emissao"),
        "ancestralidade": dados.get("ancestralidade"),
        "saude_genetica": dados.get("saude_genetica"),
        "bem_estar": dados.get("bem_estar"),
        "disclaimers": dados.get("disclaimers"),
    }


@app.get("/api/consentimento")
def ver_consentimento(requisicao: Request) -> Dict[str, Any]:
    consentimento = auditoria.obter_consentimento(pseudonimizar(sessao_da(requisicao)))
    valido = consentimento is not None and consentimento["versao_termo"] == VERSAO_TERMO
    return {
        "aceito": valido,
        "guardar_conteudo": bool(valido and consentimento["guardar_conteudo"]),
        "versao_termo": VERSAO_TERMO,
        "retencao_dias": config.RETENCAO_DIAS,
    }


@app.post("/api/consentimento")
def aceitar_consentimento(corpo: Consentimento, requisicao: Request) -> Dict[str, Any]:
    auditoria.registrar_consentimento(pseudonimizar(sessao_da(requisicao)), corpo.guardar_conteudo, VERSAO_TERMO)
    return {"aceito": True, "guardar_conteudo": corpo.guardar_conteudo, "versao_termo": VERSAO_TERMO,
            "retencao_dias": config.RETENCAO_DIAS}


@app.post("/api/perguntar")
def perguntar(corpo: Pergunta, requisicao: Request) -> Dict[str, Any]:
    sessao = sessao_da(requisicao)
    consentimento = exigir_consentimento(sessao)
    limitar_uso(sessao)
    return agentes.responder(corpo.pergunta, corpo.nivel, sessao, guardar_conteudo=consentimento["guardar_conteudo"])


@app.get("/api/resumo")
def resumo(requisicao: Request, nivel: str = "simples") -> Dict[str, Any]:
    sessao = sessao_da(requisicao)
    exigir_consentimento(sessao)
    return agentes.resumir(nivel, sessao)


@app.post("/api/feedback")
def feedback(corpo: Feedback, requisicao: Request) -> Dict[str, bool]:
    registrado = auditoria.registrar_feedback(corpo.trace_id, pseudonimizar(sessao_da(requisicao)), corpo.util)
    if not registrado:
        raise HTTPException(status_code=404, detail="Interação não encontrada para esta sessão.")
    return {"registrado": True}


@app.get("/api/meus-dados")
def meus_dados(requisicao: Request) -> Dict[str, Any]:
    """Direito de acesso (LGPD, art. 18, II): tudo o que o sistema guarda sobre a sessão."""
    return auditoria.exportar_sessao(pseudonimizar(sessao_da(requisicao)))


@app.delete("/api/meus-dados")
def apagar_meus_dados(requisicao: Request) -> Dict[str, int]:
    """Direito de eliminação (LGPD, art. 18, VI): apaga interações, eventos e consentimento."""
    return {"interacoes_apagadas": auditoria.excluir_sessao(pseudonimizar(sessao_da(requisicao)))}


@app.get("/api/monitoramento")
def monitoramento() -> Dict[str, Any]:
    """
    Indicadores operacionais agregados. Não expõe texto de perguntas nem de respostas:
    as últimas interações aparecem só com metadados.
    """
    ultimas = [
        {chave: i[chave] for chave in (
            "trace_id", "criado_em", "tipo", "intencao", "status", "provedor", "modelo",
            "prompt_versao", "uso_fallback", "latencia_ms", "etapas",
        )} | {"aprovada": i["validacao"].get("aprovada"),
              "fontes": [f["id"] for f in i["fontes"] if f.get("usada_no_contexto", True)]}
        for i in auditoria.listar_interacoes(limite=25)
    ]
    return {
        "saude": saude(),
        "metricas": auditoria.metricas(),
        "execucoes": auditoria.listar_execucoes(20),
        "eventos": auditoria.listar_eventos(20),
        "ultimas_interacoes": ultimas,
    }


@app.post("/api/pipeline/ingestao")
def reexecutar_ingestao(requisicao: Request) -> Dict[str, Any]:
    """Reexecuta o pipeline de ingestão (reindexa o relatório) e devolve o resultado etapa por etapa."""
    exigir_operador(requisicao)
    estado["ingestao"] = pipeline.executar_ingestao()
    return estado["ingestao"]


@app.get("/api/avaliacao")
def avaliacao() -> Dict[str, Any]:
    """Resultados da última avaliação do modelo, para exibição na página de governança."""
    resultados = {}
    for caminho in sorted(CAMINHO_AVALIACAO.glob("*.json")):
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        dados["pipeline"].pop("detalhe", None)
        dados["validador"].pop("detalhe", None)
        resultados[caminho.stem] = dados
    if not resultados:
        raise HTTPException(status_code=404, detail="Nenhuma avaliação executada ainda.")
    return resultados


def interacao_da_sessao(trace_id: str, sessao: str) -> Optional[Dict[str, Any]]:
    interacao = auditoria.obter_interacao(trace_id)
    return interacao if interacao and interacao["sessao"] == pseudonimizar(sessao) else None


@app.get("/api/interacoes/{trace_id}")
def interacao(trace_id: str, requisicao: Request) -> Dict[str, Any]:
    """Registro de auditoria de uma interação da própria sessão (rastreabilidade)."""
    registro = interacao_da_sessao(trace_id, sessao_da(requisicao))
    if registro is None:
        raise HTTPException(status_code=404, detail="Interação não encontrada para esta sessão.")
    return registro
