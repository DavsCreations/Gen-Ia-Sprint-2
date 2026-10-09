import json

import pytest
from fastapi.testclient import TestClient

from app import api, auditoria, config, pipeline
from app.privacidade import pseudonimizar

SESSAO = {"X-Sessao": "sessao-de-teste-123"}


@pytest.fixture
def cliente():
    with TestClient(api.app) as cliente:
        yield cliente


def test_saude_reporta_ingestao_bem_sucedida(cliente):
    corpo = cliente.get("/api/saude").json()

    assert corpo["status"] == "ok"
    assert corpo["ingestao"]["status"] == "sucesso"
    assert corpo["llm"]["provedor"] == "extrativo"


def test_relatorio_nao_expoe_identificacao_do_paciente(cliente):
    resposta = cliente.get("/api/relatorio")

    assert "Paciente Simulado" not in resposta.text
    assert "paciente" not in resposta.json()
    assert resposta.json()["ancestralidade"]["composicao"][0]["percentual"] == 62.5


def test_perguntar_exige_sessao_e_consentimento(cliente):
    pergunta = {"pergunta": "Tenho risco de diabetes?"}

    assert cliente.post("/api/perguntar", json=pergunta).status_code == 400
    assert cliente.post("/api/perguntar", json=pergunta, headers=SESSAO).status_code == 403


def test_fluxo_completo_com_consentimento(cliente):
    cliente.post("/api/consentimento", json={"guardar_conteudo": True}, headers=SESSAO)

    resposta = cliente.post("/api/perguntar", json={"pergunta": "Tenho risco de diabetes?"}, headers=SESSAO).json()

    assert resposta["status"] == "respondida"
    assert resposta["fontes"][0]["id"] == "saude:diabetes-tipo-2"
    assert resposta["explicacao"]

    assert cliente.post("/api/feedback", json={"trace_id": resposta["trace_id"], "util": True}, headers=SESSAO).status_code == 200
    assert cliente.get(f"/api/interacoes/{resposta['trace_id']}", headers=SESSAO).json()["feedback"] == 1
    # Outra sessão não enxerga a interação.
    assert cliente.get(f"/api/interacoes/{resposta['trace_id']}", headers={"X-Sessao": "outra-sessao-456"}).status_code == 404


def test_titular_exporta_e_apaga_os_proprios_dados(cliente):
    cliente.post("/api/consentimento", json={"guardar_conteudo": True}, headers=SESSAO)
    cliente.post("/api/perguntar", json={"pergunta": "Tenho risco de diabetes?"}, headers=SESSAO)

    exportado = cliente.get("/api/meus-dados", headers=SESSAO).json()
    assert len(exportado["interacoes"]) == 1
    assert exportado["consentimento"]["guardar_conteudo"] is True

    assert cliente.delete("/api/meus-dados", headers=SESSAO).json() == {"interacoes_apagadas": 1}

    depois = cliente.get("/api/meus-dados", headers=SESSAO).json()
    assert depois["interacoes"] == [] and depois["consentimento"] is None
    # Sem consentimento, o uso volta a ser bloqueado.
    assert cliente.post("/api/perguntar", json={"pergunta": "Tenho risco de diabetes?"}, headers=SESSAO).status_code == 403


def test_monitoramento_nao_expoe_texto_de_perguntas(cliente):
    cliente.post("/api/consentimento", json={"guardar_conteudo": True}, headers=SESSAO)
    cliente.post("/api/perguntar", json={"pergunta": "Tenho intolerância à lactose?"}, headers=SESSAO)

    resposta = cliente.get("/api/monitoramento")
    corpo = resposta.json()

    assert corpo["metricas"]["total_interacoes"] == 1
    assert corpo["execucoes"][0]["pipeline"] == "ingestao"
    assert "Tenho intolerância" not in resposta.text
    assert pseudonimizar(SESSAO["X-Sessao"]) not in resposta.text


def test_limite_de_perguntas_por_minuto(cliente, monkeypatch):
    monkeypatch.setattr(config, "LIMITE_POR_MINUTO", 2)
    api._janelas.clear()
    cliente.post("/api/consentimento", json={}, headers=SESSAO)

    codigos = [cliente.post("/api/perguntar", json={"pergunta": "Oi"}, headers=SESSAO).status_code for _ in range(3)]

    assert codigos == [200, 200, 429]


def test_reexecucao_do_pipeline_exige_token_de_operador(cliente, monkeypatch):
    assert cliente.post("/api/pipeline/ingestao").status_code == 403

    monkeypatch.setattr(config, "TOKEN_OPERADOR", "segredo-de-teste")
    assert cliente.post("/api/pipeline/ingestao", headers={"X-Token-Operador": "errado"}).status_code == 403
    assert cliente.post("/api/pipeline/ingestao", headers={"X-Token-Operador": "segredo-de-teste"}).json()["status"] == "sucesso"


def test_pipeline_registra_falha_quando_o_relatorio_e_invalido(tmp_path, monkeypatch):
    invalido = tmp_path / "relatorio.json"
    invalido.write_text(json.dumps({"id_relatorio": "X", "ancestralidade": {"resumo": "r"}}), encoding="utf-8")
    monkeypatch.setattr(pipeline, "CAMINHO_RELATORIO", invalido)

    resultado = pipeline.executar_ingestao()

    assert resultado["status"] == "falha"
    assert resultado["etapas"][-1]["etapa"] == "validar_estrutura"
    assert auditoria.listar_execucoes(1)[0]["status"] == "falha"
    assert auditoria.metricas()["execucoes"]["falhas"] == 1


def test_retencao_apaga_registros_antigos(cliente):
    cliente.post("/api/consentimento", json={}, headers=SESSAO)
    cliente.post("/api/perguntar", json={"pergunta": "Tenho risco de diabetes?"}, headers=SESSAO)
    with auditoria.conectar() as conexao:
        conexao.execute("UPDATE interacoes SET criado_em = '2020-01-01T00:00:00+00:00'")

    assert auditoria.aplicar_retencao(dias=30) == 1
    assert auditoria.listar_interacoes() == []
