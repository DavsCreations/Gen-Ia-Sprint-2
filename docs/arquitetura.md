# Arquitetura da Solução — GenIA

## 1. Visão Geral

O GenIA utiliza uma arquitetura baseada em RAG (Retrieval-Augmented Generation) para permitir consultas inteligentes sobre relatórios genéticos simulados.

Nesta Sprint, o foco foi implementar a camada de inteligência responsável por recuperar informações relevantes a partir de um relatório estruturado em JSON e apresentar respostas fundamentadas no conteúdo recuperado.

---

## 2. Fluxo da Arquitetura

```text
Relatório Genético Simulado (JSON)
        ↓
Data Loader
        ↓
Chunking
        ↓
Embeddings
        ↓
ChromaDB
        ↓
Busca Semântica
        ↓
Resposta Formatada
        ↓
Usuário