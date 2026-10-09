"""
Configurações centrais do GenIA: caminhos, modelos e parâmetros do RAG.
Tudo que muda entre ambientes (local, CI, deploy) é lido de variáveis de ambiente.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent

load_dotenv(RAIZ / ".env")

VERSAO_APP = "1.0.0"

CAMINHO_RELATORIO = Path(os.getenv("GENIA_RELATORIO", RAIZ / "data" / "relatorio_exemplo.json"))

# Diretório de dados de execução (banco de auditoria). Fica fora do versionamento.
DIR_EXECUCAO = Path(os.getenv("GENIA_DIR_EXECUCAO", RAIZ / "var"))
CAMINHO_BANCO = DIR_EXECUCAO / "auditoria.db"

# Embeddings. O modelo multilíngue substituiu o all-MiniLM-L6-v2 (treinado em inglês)
# após a avaliação da Sprint 4 — ver docs/avaliacao.md.
MODELO_EMBEDDING = os.getenv(
    "GENIA_EMBEDDING", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

CAMINHO_GLOSSARIO = RAIZ / "data" / "glossario.json"

# Cache em disco dos embeddings do relatório e dos exemplos de treino (nunca de perguntas).
CAMINHO_CACHE_EMBEDDINGS = Path(os.getenv("GENIA_CACHE_EMBEDDINGS", RAIZ / ".cache" / "embeddings.json"))

# Peso da busca lexical (TF-IDF) somado à similaridade semântica na pontuação final.
PESO_LEXICAL = float(os.getenv("GENIA_PESO_LEXICAL", "0.5"))

# Quantidade de trechos recuperados por pergunta.
TOP_K = int(os.getenv("GENIA_TOP_K", "3"))

# Similaridade mínima (cosseno) para considerar que o relatório cobre a pergunta.
# Calibrado em avaliacao/executar_avaliacao.py — ver docs/avaliacao.md.
SCORE_MINIMO = float(os.getenv("GENIA_SCORE_MINIMO", "0.37"))

# Sem nenhuma palavra em comum entre pergunta e trecho, a similaridade semântica precisa
# atingir este valor para o sistema considerar que o relatório cobre a pergunta.
SEMANTICO_SEM_ANCORA = float(os.getenv("GENIA_SEMANTICO_SEM_ANCORA", "0.65"))

# Retenção dos registros de auditoria, em dias (política de governança, seção de logging).
RETENCAO_DIAS = int(os.getenv("GENIA_RETENCAO_DIAS", "30"))

# Perguntas por minuto permitidas a cada sessão.
LIMITE_POR_MINUTO = int(os.getenv("GENIA_LIMITE_POR_MINUTO", "20"))

# Token exigido nas operações administrativas (reexecutar o pipeline). Vazio = desabilitadas.
TOKEN_OPERADOR = os.getenv("GENIA_TOKEN_OPERADOR", "")

# Origens autorizadas a chamar a API (front-end em deploy).
ORIGENS_PERMITIDAS = [
    o.strip() for o in os.getenv("GENIA_ORIGENS", "http://localhost:3000").split(",") if o.strip()
]
