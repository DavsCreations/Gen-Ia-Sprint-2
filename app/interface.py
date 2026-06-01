import streamlit as st
from rag import gerar_resposta_formatada


st.set_page_config(
    page_title="GenIA - Assistente Genético",
    page_icon="🧬",
    layout="centered"
)

st.title("🧬 GenIA")
st.subheader("Assistente Inteligente para Relatórios Genéticos")

st.markdown(
    """
    Este sistema utiliza **RAG**, **embeddings** e **busca semântica**
    para responder perguntas com base em um relatório genético simulado.
    """
)

st.warning(
    "As respostas possuem caráter exclusivamente informativo e não substituem avaliação médica profissional."
)

pergunta = st.text_input(
    "Digite sua pergunta sobre o relatório genético:",
    placeholder="Exemplo: Tenho risco de diabetes?"
)

if st.button("Consultar relatório"):
    if pergunta.strip() == "":
        st.error("Digite uma pergunta antes de consultar.")
    else:
        with st.spinner("Buscando informações no relatório..."):
            resposta = gerar_resposta_formatada(pergunta)

        st.success("Resposta gerada com base no relatório.")
        st.text_area("Resposta do GenIA", resposta, height=450)

st.markdown("---")
st.caption("Projeto acadêmico FIAP | Challenge Dasa/Genera | Sprint 2")