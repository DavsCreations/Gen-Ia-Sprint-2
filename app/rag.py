import hashlib
import json
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Sequence

import chromadb
from chromadb.config import Settings
from fastembed import TextEmbedding
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from app.config import (
    CAMINHO_CACHE_EMBEDDINGS,
    CAMINHO_GLOSSARIO,
    CAMINHO_RELATORIO,
    MODELO_EMBEDDING,
    PESO_LEXICAL,
    TOP_K,
)
from app.data_loader import Chunk, carregar_relatorio, criar_chunks
from app.texto import tokenizar


@dataclass
class Trecho:
    """
    Chunk recuperado pela busca, com a pontuação final e seus dois componentes:
    similaridade semântica (cosseno entre embeddings) e sobreposição lexical (TF-IDF).
    """
    chunk: Chunk
    score: float
    score_semantico: float
    score_lexical: float


@lru_cache(maxsize=4)
def carregar_modelo(nome: str = MODELO_EMBEDDING) -> TextEmbedding:
    """
    Carrega o modelo responsável por transformar textos em embeddings.
    O modelo fica em cache no processo: é carregado uma única vez, não a cada pergunta.
    """
    return TextEmbedding(model_name=nome)


_cache_embeddings: Optional[Dict[str, List[float]]] = None
_SEPARADOR = "\x1f"


def _carregar_cache() -> Dict[str, List[float]]:
    global _cache_embeddings
    if _cache_embeddings is None:
        try:
            _cache_embeddings = json.loads(CAMINHO_CACHE_EMBEDDINGS.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            _cache_embeddings = {}
    return _cache_embeddings


def _gravar_cache(cache: Dict[str, List[float]]) -> None:
    try:
        CAMINHO_CACHE_EMBEDDINGS.parent.mkdir(parents=True, exist_ok=True)
        temporario = CAMINHO_CACHE_EMBEDDINGS.with_suffix(".tmp")
        temporario.write_text(json.dumps(cache), encoding="utf-8")
        temporario.replace(CAMINHO_CACHE_EMBEDDINGS)
    except OSError:
        pass  # sistema de arquivos somente leitura: o cache continua valendo em memória


def gerar_embeddings(textos: Sequence[str], nome_modelo: str = MODELO_EMBEDDING,
                     usar_cache: bool = False) -> List[List[float]]:
    """
    Gera os embeddings dos textos.

    Com usar_cache=True os vetores são guardados em memória e em disco, o que reduz o tempo
    de subida da aplicação. Use apenas para textos do projeto (relatório, exemplos de treino),
    nunca para perguntas de usuários: elas não devem ficar gravadas em lugar algum.
    """
    if not usar_cache:
        return [vetor.tolist() for vetor in carregar_modelo(nome_modelo).embed(list(textos))]

    cache = _carregar_cache()
    faltantes = [t for t in dict.fromkeys(textos) if nome_modelo + _SEPARADOR + t not in cache]
    if faltantes:
        for texto, vetor in zip(faltantes, carregar_modelo(nome_modelo).embed(faltantes)):
            cache[nome_modelo + _SEPARADOR + texto] = vetor.tolist()
        _gravar_cache(cache)
    return [cache[nome_modelo + _SEPARADOR + t] for t in textos]


def criar_cliente_chroma():
    """
    Cria o cliente do ChromaDB em memória, com a telemetria da biblioteca desativada
    para que nenhum dado de uso saia do ambiente da aplicação.
    """
    return chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))


def carregar_glossario(caminho=CAMINHO_GLOSSARIO) -> Dict[str, List[str]]:
    """Termos leigos associados a cada chunk (ex.: "leite" para intolerância à lactose)."""
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo).get("termos", {})
    except FileNotFoundError:
        return {}


class BaseVetorial:
    """
    Base de busca de um relatório. Indexa os chunks uma vez e responde às buscas combinando
    busca semântica (ChromaDB) com busca lexical (TF-IDF).

    Os parâmetros opcionais existem para a avaliação comparar configurações
    (ver avaliacao/executar_avaliacao.py).
    """

    def __init__(self, chunks: Sequence[Chunk], nome_modelo: str = MODELO_EMBEDDING,
                 fonte: str = CAMINHO_RELATORIO.name, indexar_passagens: bool = True,
                 peso_lexical: float = PESO_LEXICAL,
                 glossario: Optional[Dict[str, List[str]]] = None):
        self.chunks = {chunk.id: chunk for chunk in chunks}
        self.ids = [chunk.id for chunk in chunks]
        self.nome_modelo = nome_modelo
        self.fonte = fonte
        self.peso_lexical = peso_lexical
        glossario = glossario or {}

        # Cada chunk entra na base como texto completo e, opcionalmente, como passagens curtas:
        # uma pergunta curta casa melhor com uma frase do que com o chunk inteiro.
        # Todo vetor aponta para o chunk pai, que é o que a busca devolve.
        entradas = []
        for chunk in chunks:
            textos = [chunk.texto] + (chunk.passagens if indexar_passagens else [])
            if glossario.get(chunk.id):
                textos.append(f"{chunk.tema}: " + ", ".join(glossario[chunk.id]))
            for i, texto in enumerate(textos):
                entradas.append((f"{chunk.id}#{i}", texto, chunk))
        self.total_vetores = len(entradas)

        # A versão identifica conteúdo + modelo: muda sempre que o relatório ou o embedding mudam.
        conteudo = nome_modelo + "".join(id_vetor + texto for id_vetor, texto, _ in entradas)
        self.versao = hashlib.sha1(conteudo.encode("utf-8")).hexdigest()[:12]

        self.colecao = criar_cliente_chroma().get_or_create_collection(
            name=f"relatorio_{self.versao}",
            metadata={"hnsw:space": "cosine"},
        )

        if self.colecao.count() == 0 and entradas:
            self.colecao.add(
                ids=[id_vetor for id_vetor, _, _ in entradas],
                documents=[texto for _, texto, _ in entradas],
                embeddings=gerar_embeddings([texto for _, texto, _ in entradas], nome_modelo, usar_cache=True),
                metadatas=[
                    {"fonte": fonte, "chunk": chunk.id, "secao": chunk.secao, "tema": chunk.tema}
                    for _, _, chunk in entradas
                ],
            )

        # Índice lexical: um documento por chunk (texto + termos do glossário).
        self.tfidf = None
        if peso_lexical > 0 and chunks:
            documentos = [
                chunk.texto + " " + " ".join(glossario.get(chunk.id, [])) for chunk in chunks
            ]
            self.tfidf = TfidfVectorizer(tokenizer=tokenizar, lowercase=False, token_pattern=None)
            self.matriz_tfidf = self.tfidf.fit_transform(documentos)

    def _scores_semanticos(self, pergunta: str) -> Dict[str, float]:
        resultado = self.colecao.query(
            query_embeddings=gerar_embeddings([pergunta], self.nome_modelo),
            n_results=self.total_vetores,
        )
        # O score do chunk é o do seu vetor mais próximo da pergunta.
        melhores: Dict[str, float] = {}
        for metadado, distancia in zip(resultado["metadatas"][0], resultado["distances"][0]):
            melhores.setdefault(metadado["chunk"], 1 - distancia)
        return melhores

    def _scores_lexicais(self, pergunta: str) -> Dict[str, float]:
        if self.tfidf is None:
            return {}
        similaridades = linear_kernel(self.tfidf.transform([pergunta]), self.matriz_tfidf)[0]
        return dict(zip(self.ids, similaridades.tolist()))

    def buscar(self, pergunta: str, quantidade_resultados: int = TOP_K) -> List[Trecho]:
        """
        Recebe uma pergunta do usuário e busca os trechos mais relevantes do relatório.
        Pontuação final = similaridade semântica + peso_lexical * similaridade lexical.
        """
        semanticos = self._scores_semanticos(pergunta)
        lexicais = self._scores_lexicais(pergunta)

        trechos = []
        for id_chunk in self.ids:
            semantico = semanticos.get(id_chunk, 0.0)
            lexical = lexicais.get(id_chunk, 0.0)
            trechos.append(Trecho(
                chunk=self.chunks[id_chunk],
                score=round(min(1.0, semantico + self.peso_lexical * lexical), 4),
                score_semantico=round(semantico, 4),
                score_lexical=round(lexical, 4),
            ))

        trechos.sort(key=lambda trecho: trecho.score, reverse=True)
        return trechos[:quantidade_resultados]


_base: Optional[BaseVetorial] = None
_trava = threading.Lock()


def preparar_base_vetorial(recriar: bool = False) -> BaseVetorial:
    """
    Lê o relatório, cria os chunks, gera embeddings e armazena na base vetorial.
    A base é construída uma vez por processo; use recriar=True para reindexar.
    """
    global _base

    with _trava:
        if _base is None or recriar:
            relatorio = carregar_relatorio(CAMINHO_RELATORIO)
            _base = BaseVetorial(criar_chunks(relatorio), glossario=carregar_glossario())
        return _base


def buscar_contexto(pergunta: str, quantidade_resultados: int = TOP_K) -> List[Trecho]:
    return preparar_base_vetorial().buscar(pergunta, quantidade_resultados)


if __name__ == "__main__":
    pergunta = "Tenho risco de diabetes?"
    for trecho in buscar_contexto(pergunta):
        print(f"{trecho.score:.3f}  {trecho.chunk.id}")
