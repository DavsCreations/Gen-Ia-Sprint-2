import copy

from app.data_loader import carregar_relatorio, criar_chunks, validar_relatorio
from app.privacidade import mascarar_pii, pseudonimizar
from app.rag import buscar_contexto


def test_percentuais_de_ancestralidade_sao_indexados():
    # Regressão do defeito da Sprint 2: a chave "composição" (com acento) nunca era encontrada.
    chunks = {c.id: c for c in criar_chunks(carregar_relatorio())}

    assert "62,5%" in chunks["ancestralidade:visao-geral"].texto
    assert {"ancestralidade:europeia", "ancestralidade:africana"} <= chunks.keys()


def test_nivel_de_risco_entra_no_chunk():
    chunks = {c.id: c for c in criar_chunks(carregar_relatorio())}

    assert "Nível de risco: Moderado" in chunks["saude:diabetes-tipo-2"].texto


def test_dados_do_paciente_nao_sao_indexados():
    textos = " ".join(c.texto for c in criar_chunks(carregar_relatorio()))

    assert "Paciente Simulado" not in textos


def test_relatorio_de_exemplo_e_valido():
    assert validar_relatorio(carregar_relatorio()) == []


def test_validacao_acusa_chave_com_grafia_divergente():
    relatorio = copy.deepcopy(carregar_relatorio())
    relatorio["ancestralidade"]["composição"] = relatorio["ancestralidade"].pop("composicao")

    problemas = validar_relatorio(relatorio)

    assert any(p["nivel"] == "aviso" and "composição" in p["caminho"] for p in problemas)
    assert any(p["nivel"] == "erro" and p["caminho"] == "ancestralidade.composicao" for p in problemas)


def test_validacao_acusa_campo_ausente_e_percentuais_incoerentes():
    relatorio = copy.deepcopy(carregar_relatorio())
    del relatorio["saude_genetica"][0]["recomendacao"]
    relatorio["ancestralidade"]["composicao"][0]["percentual"] = 10

    mensagens = [p["mensagem"] for p in validar_relatorio(relatorio)]

    assert "campo obrigatório ausente: recomendacao" in mensagens
    assert any("percentuais somam" in m for m in mensagens)


def test_busca_encontra_tema_por_termo_leigo():
    assert buscar_contexto("Leite me faz mal?")[0].chunk.id == "bem-estar:intolerancia-a-lactose"
    assert buscar_contexto("Tenho pressão alta?")[0].chunk.id == "saude:hipertensao-arterial"


def test_mascaramento_de_dados_pessoais():
    texto, tipos = mascarar_pii("Meu CPF é 123.456.789-09, e-mail ana@exemplo.com.br e fone (11) 98765-4321. Tenho risco?")

    assert "123.456.789-09" not in texto and "ana@exemplo.com.br" not in texto and "98765-4321" not in texto
    assert tipos == ["cpf", "email", "telefone"]


def test_mascaramento_preserva_pergunta_sem_dados_pessoais():
    assert mascarar_pii("Tenho risco de diabetes tipo 2?") == ("Tenho risco de diabetes tipo 2?", [])


def test_pseudonimo_e_estavel_e_nao_expoe_a_sessao():
    assert pseudonimizar("sessao-abc") == pseudonimizar("sessao-abc")
    assert pseudonimizar("sessao-abc") != pseudonimizar("sessao-abd")
    assert "sessao-abc" not in pseudonimizar("sessao-abc")
