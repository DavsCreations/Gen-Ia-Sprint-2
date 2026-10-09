"""
Registro de auditoria do GenIA (logging estruturado).

Cada interação, execução de pipeline e evento relevante é gravado em SQLite e também
emitido como uma linha JSON no log da aplicação (stdout), que a plataforma de deploy coleta.

O que NÃO é gravado: o identificador original da sessão (apenas o pseudônimo) e dados
pessoais digitados na pergunta (mascarados antes). O texto da pergunta e da resposta só é
gravado quando o titular autorizou; sem autorização ficam apenas os metadados.
"""
import json
import logging
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional

from app import config

logger = logging.getLogger("genia")
if not logger.handlers:
    _saida = logging.StreamHandler(sys.stdout)
    _saida.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_saida)
    logger.setLevel(logging.INFO)
    logger.propagate = False

ESQUEMA = """
CREATE TABLE IF NOT EXISTS interacoes (
    trace_id        TEXT PRIMARY KEY,
    sessao          TEXT NOT NULL,
    criado_em       TEXT NOT NULL,
    tipo            TEXT NOT NULL,
    pergunta        TEXT,
    resposta        TEXT,
    conteudo_gravado INTEGER NOT NULL,
    nivel           TEXT,
    intencao        TEXT,
    status          TEXT NOT NULL,
    fontes          TEXT NOT NULL,
    validacao       TEXT NOT NULL,
    etapas          TEXT NOT NULL,
    pii_mascarada   TEXT NOT NULL,
    provedor        TEXT,
    modelo          TEXT,
    prompt_versao   TEXT,
    embedding       TEXT,
    base_versao     TEXT,
    uso_fallback    INTEGER NOT NULL,
    latencia_ms     INTEGER NOT NULL,
    feedback        INTEGER
);
CREATE INDEX IF NOT EXISTS idx_interacoes_sessao ON interacoes (sessao);
CREATE INDEX IF NOT EXISTS idx_interacoes_criado ON interacoes (criado_em);

CREATE TABLE IF NOT EXISTS execucoes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline    TEXT NOT NULL,
    iniciado_em TEXT NOT NULL,
    duracao_ms  INTEGER NOT NULL,
    status      TEXT NOT NULL,
    etapas      TEXT NOT NULL,
    erro        TEXT
);

CREATE TABLE IF NOT EXISTS eventos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    criado_em TEXT NOT NULL,
    tipo      TEXT NOT NULL,
    sessao    TEXT,
    detalhe   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consentimentos (
    sessao           TEXT PRIMARY KEY,
    aceito_em        TEXT NOT NULL,
    versao_termo     TEXT NOT NULL,
    guardar_conteudo INTEGER NOT NULL
);
"""

CAMPOS_JSON = ("fontes", "validacao", "etapas", "pii_mascarada")


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    config.DIR_EXECUCAO.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(config.CAMINHO_BANCO, timeout=10)
    conexao.row_factory = sqlite3.Row
    try:
        conexao.executescript(ESQUEMA)
        yield conexao
        conexao.commit()
    finally:
        conexao.close()


def _emitir(tipo: str, dados: Dict[str, Any]) -> None:
    logger.info(json.dumps({"log": tipo, "em": agora(), **dados}, ensure_ascii=False))


def registrar_interacao(registro: Dict[str, Any]) -> None:
    """Grava uma interação (pergunta ou resumo) com tudo que explica como a resposta foi produzida."""
    gravar = bool(registro.get("conteudo_gravado"))
    linha = {
        "trace_id": registro["trace_id"],
        "sessao": registro["sessao"],
        "criado_em": agora(),
        "tipo": registro.get("tipo", "pergunta"),
        "pergunta": registro.get("pergunta") if gravar else None,
        "resposta": registro.get("resposta") if gravar else None,
        "conteudo_gravado": int(gravar),
        "nivel": registro.get("nivel"),
        "intencao": registro.get("intencao"),
        "status": registro["status"],
        "fontes": json.dumps(registro.get("fontes", []), ensure_ascii=False),
        "validacao": json.dumps(registro.get("validacao", {}), ensure_ascii=False),
        "etapas": json.dumps(registro.get("etapas", []), ensure_ascii=False),
        "pii_mascarada": json.dumps(registro.get("pii_mascarada", [])),
        "provedor": registro.get("provedor"),
        "modelo": registro.get("modelo"),
        "prompt_versao": registro.get("prompt_versao"),
        "embedding": registro.get("embedding"),
        "base_versao": registro.get("base_versao"),
        "uso_fallback": int(bool(registro.get("uso_fallback"))),
        "latencia_ms": int(registro.get("latencia_ms", 0)),
    }
    colunas = ", ".join(linha)
    marcadores = ", ".join(f":{coluna}" for coluna in linha)
    with conectar() as conexao:
        conexao.execute(f"INSERT INTO interacoes ({colunas}) VALUES ({marcadores})", linha)

    # No log de aplicação vão apenas metadados: nunca o texto da pergunta ou da resposta.
    _emitir("interacao", {
        chave: linha[chave] for chave in (
            "trace_id", "sessao", "tipo", "intencao", "status", "provedor", "modelo",
            "prompt_versao", "base_versao", "uso_fallback", "latencia_ms",
        )
    })


def registrar_execucao(pipeline: str, status: str, etapas: List[Dict[str, Any]],
                       duracao_ms: int, erro: Optional[str] = None) -> None:
    """Grava a execução de um pipeline (ingestão, avaliação, retenção), etapa por etapa."""
    with conectar() as conexao:
        conexao.execute(
            "INSERT INTO execucoes (pipeline, iniciado_em, duracao_ms, status, etapas, erro) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pipeline, agora(), int(duracao_ms), status, json.dumps(etapas, ensure_ascii=False), erro),
        )
    _emitir("execucao", {"pipeline": pipeline, "status": status, "duracao_ms": int(duracao_ms), "erro": erro})


def registrar_evento(tipo: str, detalhe: Dict[str, Any], sessao: Optional[str] = None) -> None:
    with conectar() as conexao:
        conexao.execute(
            "INSERT INTO eventos (criado_em, tipo, sessao, detalhe) VALUES (?, ?, ?, ?)",
            (agora(), tipo, sessao, json.dumps(detalhe, ensure_ascii=False)),
        )
    _emitir("evento", {"tipo": tipo, "sessao": sessao, **detalhe})


def registrar_consentimento(sessao: str, guardar_conteudo: bool, versao_termo: str) -> Dict[str, Any]:
    with conectar() as conexao:
        conexao.execute(
            "INSERT INTO consentimentos (sessao, aceito_em, versao_termo, guardar_conteudo) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(sessao) DO UPDATE SET aceito_em = excluded.aceito_em, "
            "versao_termo = excluded.versao_termo, guardar_conteudo = excluded.guardar_conteudo",
            (sessao, agora(), versao_termo, int(guardar_conteudo)),
        )
    registrar_evento("consentimento", {"guardar_conteudo": guardar_conteudo, "versao_termo": versao_termo}, sessao)
    return obter_consentimento(sessao)


def obter_consentimento(sessao: str) -> Optional[Dict[str, Any]]:
    with conectar() as conexao:
        linha = conexao.execute("SELECT * FROM consentimentos WHERE sessao = ?", (sessao,)).fetchone()
    if linha is None:
        return None
    return {**dict(linha), "guardar_conteudo": bool(linha["guardar_conteudo"])}


def registrar_feedback(trace_id: str, sessao: str, util: bool) -> bool:
    with conectar() as conexao:
        cursor = conexao.execute(
            "UPDATE interacoes SET feedback = ? WHERE trace_id = ? AND sessao = ?",
            (int(util), trace_id, sessao),
        )
        return cursor.rowcount > 0


def _interacao(linha: sqlite3.Row) -> Dict[str, Any]:
    dados = dict(linha)
    for campo in CAMPOS_JSON:
        dados[campo] = json.loads(dados[campo])
    dados["conteudo_gravado"] = bool(dados["conteudo_gravado"])
    dados["uso_fallback"] = bool(dados["uso_fallback"])
    return dados


def listar_interacoes(sessao: Optional[str] = None, limite: int = 50) -> List[Dict[str, Any]]:
    consulta = "SELECT * FROM interacoes"
    parametros: tuple = ()
    if sessao:
        consulta += " WHERE sessao = ?"
        parametros = (sessao,)
    consulta += " ORDER BY criado_em DESC LIMIT ?"
    with conectar() as conexao:
        linhas = conexao.execute(consulta, (*parametros, limite)).fetchall()
    return [_interacao(linha) for linha in linhas]


def obter_interacao(trace_id: str) -> Optional[Dict[str, Any]]:
    with conectar() as conexao:
        linha = conexao.execute("SELECT * FROM interacoes WHERE trace_id = ?", (trace_id,)).fetchone()
    return _interacao(linha) if linha else None


def exportar_sessao(sessao: str) -> Dict[str, Any]:
    """Tudo o que o sistema guarda sobre uma sessão (direito de acesso do titular)."""
    with conectar() as conexao:
        eventos = conexao.execute(
            "SELECT criado_em, tipo, detalhe FROM eventos WHERE sessao = ? ORDER BY id", (sessao,)
        ).fetchall()
    return {
        "sessao": sessao,
        "exportado_em": agora(),
        "consentimento": obter_consentimento(sessao),
        "interacoes": listar_interacoes(sessao, limite=1000),
        "eventos": [{**dict(e), "detalhe": json.loads(e["detalhe"])} for e in eventos],
    }


def excluir_sessao(sessao: str) -> int:
    """Apaga interações, eventos e consentimento de uma sessão (direito de eliminação)."""
    with conectar() as conexao:
        apagadas = conexao.execute("DELETE FROM interacoes WHERE sessao = ?", (sessao,)).rowcount
        conexao.execute("DELETE FROM eventos WHERE sessao = ?", (sessao,))
        conexao.execute("DELETE FROM consentimentos WHERE sessao = ?", (sessao,))
    # O evento de exclusão fica sem vínculo com a sessão: registra que houve o pedido, não de quem.
    registrar_evento("exclusao_dados", {"interacoes_apagadas": apagadas})
    return apagadas


def aplicar_retencao(dias: Optional[int] = None) -> int:
    """Apaga registros mais antigos que o prazo de retenção."""
    dias = config.RETENCAO_DIAS if dias is None else dias
    limite = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat(timespec="seconds")
    inicio = time.perf_counter()
    with conectar() as conexao:
        apagadas = conexao.execute("DELETE FROM interacoes WHERE criado_em < ?", (limite,)).rowcount
        conexao.execute("DELETE FROM eventos WHERE criado_em < ?", (limite,))
        conexao.execute("DELETE FROM execucoes WHERE iniciado_em < ?", (limite,))
    registrar_execucao(
        "retencao", "sucesso",
        [{"etapa": "apagar_registros_antigos", "status": "sucesso",
          "detalhe": f"{apagadas} interações anteriores a {limite}"}],
        (time.perf_counter() - inicio) * 1000,
    )
    return apagadas


def listar_execucoes(limite: int = 30) -> List[Dict[str, Any]]:
    with conectar() as conexao:
        linhas = conexao.execute("SELECT * FROM execucoes ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    return [{**dict(linha), "etapas": json.loads(linha["etapas"])} for linha in linhas]


def listar_eventos(limite: int = 30) -> List[Dict[str, Any]]:
    with conectar() as conexao:
        linhas = conexao.execute(
            "SELECT id, criado_em, tipo, detalhe FROM eventos ORDER BY id DESC LIMIT ?", (limite,)
        ).fetchall()
    return [{**dict(linha), "detalhe": json.loads(linha["detalhe"])} for linha in linhas]


def metricas() -> Dict[str, Any]:
    """Indicadores operacionais calculados a partir do registro de auditoria."""
    with conectar() as conexao:
        linhas = conexao.execute(
            "SELECT status, intencao, validacao, uso_fallback, latencia_ms, feedback, provedor, "
            "criado_em FROM interacoes WHERE tipo = 'pergunta'"
        ).fetchall()
        execucoes = conexao.execute("SELECT status FROM execucoes").fetchall()

    total = len(linhas)
    latencias = sorted(linha["latencia_ms"] for linha in linhas)
    por_status: Dict[str, int] = {}
    por_intencao: Dict[str, int] = {}
    por_dia: Dict[str, int] = {}
    reprovadas = 0
    for linha in linhas:
        por_status[linha["status"]] = por_status.get(linha["status"], 0) + 1
        por_intencao[linha["intencao"] or "indefinida"] = por_intencao.get(linha["intencao"] or "indefinida", 0) + 1
        por_dia[linha["criado_em"][:10]] = por_dia.get(linha["criado_em"][:10], 0) + 1
        if json.loads(linha["validacao"]).get("tentativas_reprovadas"):
            reprovadas += 1

    def percentil(p: float) -> int:
        if not latencias:
            return 0
        return latencias[min(len(latencias) - 1, int(round(p * (len(latencias) - 1))))]

    avaliadas = [linha["feedback"] for linha in linhas if linha["feedback"] is not None]

    return {
        "total_interacoes": total,
        "por_status": por_status,
        "por_intencao": por_intencao,
        "por_dia": dict(sorted(por_dia.items())),
        "latencia_ms": {"p50": percentil(0.5), "p95": percentil(0.95), "max": latencias[-1] if latencias else 0},
        "uso_fallback": sum(linha["uso_fallback"] for linha in linhas),
        "respostas_reprovadas_na_auditoria": reprovadas,
        "feedback": {"avaliadas": len(avaliadas), "uteis": sum(avaliadas)},
        "execucoes": {
            "total": len(execucoes),
            "falhas": sum(1 for e in execucoes if e["status"] != "sucesso"),
        },
    }
