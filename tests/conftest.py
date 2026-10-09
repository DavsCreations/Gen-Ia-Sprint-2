import pytest

from app import agentes, config, llm


@pytest.fixture(autouse=True)
def ambiente_isolado(tmp_path, monkeypatch):
    """Cada teste usa um banco de auditoria próprio e roda sem LLM, salvo quando simula um."""
    monkeypatch.setattr(config, "DIR_EXECUCAO", tmp_path)
    monkeypatch.setattr(config, "CAMINHO_BANCO", tmp_path / "auditoria.db")
    monkeypatch.setattr(config, "URL_BANCO", "")
    monkeypatch.setenv("LLM_PROVIDER", "extrativo")
    agentes._resumos.clear()


@pytest.fixture
def llm_simulado(monkeypatch):
    """
    Substitui o LLM por uma fila de respostas prontas. Devolve a lista de chamadas recebidas.
    Um item da fila que seja uma exceção é lançado em vez de devolvido.
    """
    def preparar(*respostas):
        fila, chamadas = list(respostas), []
        monkeypatch.setattr(llm, "config_atual", lambda: llm.ConfigLLM("simulado", "modelo-de-teste", "http://teste"))

        def gerar(mensagens, config=None, temperatura=None, max_tokens=500):
            chamadas.append(mensagens)
            resposta = fila.pop(0)
            if isinstance(resposta, Exception):
                raise resposta
            return resposta

        monkeypatch.setattr(llm, "gerar", gerar)
        return chamadas

    return preparar
