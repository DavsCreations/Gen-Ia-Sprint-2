import os
import sys
import chromadb

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sentence_transformers import SentenceTransformer
from app.data_loader import carregar_relatorio, criar_chunks


CAMINHO_RELATORIO = "data/relatorio_exemplo.json"
NOME_COLECAO = "relatorio_genetico"


def carregar_modelo():
    """
    Carrega o modelo responsável por transformar textos em embeddings.
    """
    modelo = SentenceTransformer("all-MiniLM-L6-v2")
    return modelo


def criar_cliente_chroma():
    """
    Cria o cliente do ChromaDB.
    Nesta versão, usamos o banco em memória para simplificar a demonstração.
    """
    cliente = chromadb.Client()
    return cliente


def preparar_base_vetorial():
    """
    Lê o relatório, cria os chunks, gera embeddings e armazena na base vetorial.
    """
    relatorio = carregar_relatorio(CAMINHO_RELATORIO)
    chunks = criar_chunks(relatorio)

    modelo = carregar_modelo()
    cliente = criar_cliente_chroma()

    colecao = cliente.get_or_create_collection(name=NOME_COLECAO)

    ids_existentes = colecao.get()["ids"]

    for i, chunk in enumerate(chunks):
        id_chunk = f"chunk_{i + 1}"

        if id_chunk in ids_existentes:
            continue

        embedding = modelo.encode(chunk).tolist()

        colecao.add(
            ids=[id_chunk],
            documents=[chunk],
            embeddings=[embedding],
            metadatas=[
                {
                    "fonte": "relatorio_exemplo.json",
                    "chunk": i + 1
                }
            ]
        )

    return colecao, modelo


def buscar_contexto(pergunta, quantidade_resultados=1):
    """
    Recebe uma pergunta do usuário e busca o trecho mais parecido na base vetorial.
    """
    colecao, modelo = preparar_base_vetorial()

    embedding_pergunta = modelo.encode(pergunta).tolist()

    resultado = colecao.query(
        query_embeddings=[embedding_pergunta],
        n_results=quantidade_resultados
    )

    documentos = resultado["documents"][0]
    metadados = resultado["metadatas"][0]

    return documentos, metadados


def gerar_resposta_formatada(pergunta):
    """
    Gera uma resposta simples, fundamentada no trecho recuperado pela busca semântica.
    """
    documentos, metadados = buscar_contexto(pergunta)

    contexto = documentos[0]
    metadado = metadados[0]

    resposta = f"""
PERGUNTA DO USUÁRIO:
{pergunta}

RESPOSTA DO ASSISTENTE:
Com base no relatório genético analisado, o sistema encontrou o seguinte trecho relacionado à sua pergunta:

{contexto}

EXPLICAÇÃO SIMPLIFICADA:
Esse resultado representa uma informação genética interpretativa. Ele não deve ser entendido como diagnóstico definitivo.

A predisposição genética indica uma possibilidade aumentada ou reduzida associada a determinados fatores, mas não confirma a presença de uma doença. Hábitos de vida, histórico familiar, ambiente e acompanhamento profissional também influenciam os resultados de saúde.

FONTE UTILIZADA:
Arquivo: {metadado["fonte"]}
Chunk: {metadado["chunk"]}

AVISO:
Esta resposta possui caráter exclusivamente informativo e não substitui avaliação médica profissional.
"""

    return resposta


if __name__ == "__main__":
    pergunta = "Tenho risco de diabetes?"
    resposta = gerar_resposta_formatada(pergunta)
    print(resposta)