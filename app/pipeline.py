"""
Pipeline de ingestão do relatório, com monitoramento etapa por etapa.

Executado na subida da aplicação e pela automação (python -m app.pipeline). Cada etapa
registra status, duração e detalhe; o resultado vai para o log de auditoria e alimenta a
página de monitoramento. Uma etapa com falha interrompe o pipeline e devolve código de saída 1.
"""
import sys
import time
from typing import Any, Callable, Dict, List

from app import auditoria, intencao, validador
from app.config import CAMINHO_RELATORIO, MODELO_EMBEDDING
from app.data_loader import carregar_relatorio, criar_chunks, validar_relatorio
from app.rag import preparar_base_vetorial

# Busca de verificação: se a base estiver correta, esta pergunta devolve este trecho em primeiro.
PERGUNTA_VERIFICACAO = "Tenho predisposição a diabetes tipo 2?"
TRECHO_ESPERADO = "saude:diabetes-tipo-2"


class FalhaPipeline(Exception):
    pass


def executar_ingestao(registrar: bool = True) -> Dict[str, Any]:
    inicio = time.perf_counter()
    etapas: List[Dict[str, Any]] = []
    estado: Dict[str, Any] = {}

    def etapa(nome: str, funcao: Callable[[], str]) -> None:
        comeco = time.perf_counter()
        try:
            detalhe, status = funcao(), "sucesso"
        except Exception as erro:  # qualquer falha é registrada antes de interromper
            detalhe, status = f"{type(erro).__name__}: {erro}", "falha"
        etapas.append({
            "etapa": nome, "status": status, "detalhe": detalhe,
            "duracao_ms": round((time.perf_counter() - comeco) * 1000),
        })
        if status == "falha":
            raise FalhaPipeline(f"{nome}: {detalhe}")

    def carregar() -> str:
        estado["relatorio"] = carregar_relatorio(CAMINHO_RELATORIO)
        return f"{CAMINHO_RELATORIO.name} lido"

    def validar() -> str:
        problemas = validar_relatorio(estado["relatorio"])
        erros = [p for p in problemas if p["nivel"] == "erro"]
        avisos = [p for p in problemas if p["nivel"] == "aviso"]
        estado["avisos"] = avisos
        if erros:
            raise ValueError("; ".join(f"{p['caminho']}: {p['mensagem']}" for p in erros))
        if avisos:
            return f"{len(avisos)} aviso(s): " + "; ".join(f"{p['caminho']}: {p['mensagem']}" for p in avisos)
        return "estrutura válida, sem avisos"

    def dividir() -> str:
        estado["chunks"] = criar_chunks(estado["relatorio"])
        if not estado["chunks"]:
            raise ValueError("nenhum chunk gerado")
        return f"{len(estado['chunks'])} chunks"

    def indexar() -> str:
        estado["base"] = preparar_base_vetorial(recriar=True)
        return f"{estado['base'].total_vetores} vetores, versão {estado['base'].versao}, modelo {MODELO_EMBEDDING}"

    def treinar() -> str:
        intencao.obter_classificador.cache_clear()
        modelo = intencao.obter_classificador()
        return f"classes: {', '.join(modelo.classes_)}"

    def aquecer() -> str:
        return f"{validador.aquecer(estado['chunks'])} passagens em cache"

    def verificar() -> str:
        trechos = estado["base"].buscar(PERGUNTA_VERIFICACAO, 1)
        if not trechos or trechos[0].chunk.id != TRECHO_ESPERADO:
            obtido = trechos[0].chunk.id if trechos else "nada"
            raise ValueError(f"busca de verificação devolveu {obtido}, esperado {TRECHO_ESPERADO}")
        return f"busca de verificação correta (pontuação {trechos[0].score:.2f})"

    status, erro = "sucesso", None
    try:
        etapa("carregar_relatorio", carregar)
        etapa("validar_estrutura", validar)
        etapa("criar_chunks", dividir)
        etapa("indexar_base_vetorial", indexar)
        etapa("treinar_classificador_de_intencao", treinar)
        etapa("aquecer_validador", aquecer)
        etapa("busca_de_verificacao", verificar)
    except FalhaPipeline as falha:
        status, erro = "falha", str(falha)

    duracao_ms = round((time.perf_counter() - inicio) * 1000)
    if registrar:
        auditoria.registrar_execucao("ingestao", status, etapas, duracao_ms, erro)

    return {"pipeline": "ingestao", "status": status, "erro": erro, "duracao_ms": duracao_ms, "etapas": etapas}


if __name__ == "__main__":
    resultado = executar_ingestao()
    for item in resultado["etapas"]:
        print(f"[{item['status'].upper():7}] {item['etapa']:36} {item['duracao_ms']:>6} ms  {item['detalhe']}")
    print(f"\nPipeline de ingestão: {resultado['status']} em {resultado['duracao_ms']} ms")
    sys.exit(0 if resultado["status"] == "sucesso" else 1)
