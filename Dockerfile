# Imagem da API do GenIA (FastAPI). O front-end (web/) é publicado à parte.
# Serve na porta 80 por padrão (exigência da Vercel) ou na porta indicada pela variável PORT.
FROM python:3.14-slim

WORKDIR /srv

ENV PYTHONUNBUFFERED=1 \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1 \
    FASTEMBED_CACHE_PATH=/srv/.cache/fastembed \
    GENIA_CACHE_EMBEDDINGS=/srv/.cache/embeddings.json \
    GENIA_DIR_EXECUCAO=/tmp/genia

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
COPY data data
COPY avaliacao avaliacao

# Roda o pipeline de ingestão durante o build: baixa o modelo de embeddings e grava em cache os
# vetores do relatório. A subida do contêiner fica rápida e não depende de rede; e, se o relatório
# estiver inválido, o build falha em vez de publicar uma aplicação quebrada.
RUN LLM_PROVIDER=extrativo python -m app.pipeline

EXPOSE 80
CMD ["sh", "-c", "uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-80}"]
