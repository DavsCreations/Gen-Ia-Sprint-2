# FIAP - Faculdade de Informática e Administração Paulista

<p align="center">
<a href="https://www.fiap.com.br/">
<img src="assets/logo-fiap.png" alt="FIAP" width="40%">
</a>
</p>

<br>

# 🧬 GenIA — Assistente Inteligente para Relatórios Genéticos

## Grupo 48 - Graduação 1TIAOB - 2025/2 - Turma A

---

## 👨‍🎓 Integrantes

- Davi Rocha — RM566336
- Daniel Caffé — RM564440
- Enrico — RM561352

---

## 👩‍🏫 Professores

### Tutor

- CaiqueFiap-2026

### Coordenador

- FIAP Challenge Sprint

---

# 📜 Descrição

O **GenIA** é um assistente inteligente desenvolvido para apoiar a interpretação de relatórios genéticos simulados da Genera, dentro do Challenge Sprint FIAP em parceria com a Dasa.

A proposta do projeto é permitir que o usuário faça perguntas em linguagem natural sobre um relatório genético e receba respostas organizadas, acessíveis e fundamentadas nos dados disponíveis no próprio relatório.

Nesta Sprint 2, o foco foi construir a camada de inteligência da solução, utilizando conceitos de **Processamento de Linguagem Natural**, **embeddings**, **base vetorial**, **busca semântica** e **Retrieval-Augmented Generation (RAG)**.

A solução desenvolvida realiza:

- Leitura de relatório genético simulado em JSON;
- Separação do conteúdo em chunks;
- Geração de embeddings com Sentence Transformers;
- Armazenamento vetorial com ChromaDB;
- Busca semântica a partir da pergunta do usuário;
- Resposta baseada no trecho mais relevante do relatório;
- Exibição da fonte utilizada na resposta;
- Interface web simples utilizando Streamlit;
- Aplicação de avisos de segurança e governança.

O projeto não realiza diagnóstico médico e não substitui avaliação profissional. As respostas possuem caráter exclusivamente informativo e educacional.

---

# 🎯 Objetivo da Sprint 2

Implementar a camada de inteligência do sistema GenIA, permitindo que o usuário consulte informações de um relatório genético por meio de perguntas em linguagem natural.

Os principais objetivos técnicos foram:

- Implementar uma estrutura RAG;
- Desenvolver busca semântica;
- Utilizar embeddings para representação vetorial dos textos;
- Criar uma base vetorial com ChromaDB;
- Construir uma interface funcional de consulta;
- Garantir rastreabilidade das respostas;
- Aplicar limites de governança para evitar interpretações médicas indevidas.

---

# 🧠 Arquitetura da Solução

Fluxo geral da aplicação:

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
  Interface Streamlit
            ↓
         Usuário
```

---

# ⚙️ Tecnologias Utilizadas

## Linguagem

- Python 3.12

## Inteligência Artificial / NLP

- Sentence Transformers
- Embeddings
- Busca Semântica
- RAG

## Banco Vetorial

- ChromaDB

## Interface

- Streamlit

## Dados

- JSON simulado

## Versionamento

- Git
- GitHub

---

# 📁 Estrutura de Pastas

```text
Gen-Ia-Sprint-2
│
├── app
│   ├── data_loader.py
│   ├── rag.py
│   ├── main.py
│   ├── interface.py
│   └── prompts.py
│
├── data
│   └── relatorio_exemplo.json
│
├── docs
│   ├── arquitetura.md
│   ├── governanca.md
│   └── riscos.md
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

# 🔧 Como Executar o Projeto

## 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
```

## 2. Acessar a pasta do projeto

```bash
cd Gen-Ia-Sprint-2
```

## 3. Criar ambiente virtual

```bash
python -m venv .venv
```

## 4. Ativar ambiente virtual

Windows PowerShell:

```bash
.\.venv\Scripts\activate
```

Caso haja erro de permissão no PowerShell:

```bash
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Depois tente ativar novamente:

```bash
.\.venv\Scripts\activate
```

## 5. Instalar dependências

```bash
pip install -r requirements.txt
```

## 6. Executar interface web

```bash
streamlit run app/interface.py
```

A aplicação será aberta em:

```text
http://localhost:8501
```

---

# 💬 Exemplos de Perguntas

```text
Tenho risco de diabetes?

Tenho intolerância à lactose?

Qual é minha ancestralidade?

Posso consumir cafeína?

O relatório indica algo sobre hipertensão?
```

---

# 🔒 Governança e Segurança

O GenIA foi desenvolvido considerando o contexto sensível de dados genéticos.

Diretrizes aplicadas:

- Não realiza diagnóstico médico;
- Não prescreve tratamentos;
- Não substitui profissionais da saúde;
- Utiliza apenas informações presentes no relatório;
- Apresenta aviso de caráter informativo;
- Exibe a fonte utilizada na resposta;
- Trabalha apenas com dados simulados nesta Sprint.

---

# 📊 Resultados Obtidos

Durante a Sprint 2, foram implementados:

- Pipeline de leitura de relatório JSON;
- Transformação do relatório em chunks;
- Geração de embeddings;
- Armazenamento em base vetorial;
- Busca semântica funcional;
- Resposta fundamentada no relatório;
- Chat via terminal;
- Interface web com Streamlit;
- Exibição de fonte e chunk utilizado;
- Disclaimer de segurança médica.

---

# 🚀 Evolução da Sprint

## Sprint 1

- Estruturação inicial dos dados;
- Conversão de informações do relatório para formato JSON;
- Organização da proposta técnica.

## Sprint 2

- Implementação da camada RAG;
- Criação da busca semântica;
- Uso de embeddings;
- Integração com ChromaDB;
- Criação de interface de consulta;
- Documentação de arquitetura, governança e riscos.

---

# 🎥 Demonstração

Link do vídeo:

```text
Adicionar link do vídeo não listado após a publicação.
```

---

# 🗃 Histórico de Lançamentos

## 0.2.0 - Sprint 2

- Implementação do sistema RAG;
- Criação da base vetorial;
- Busca semântica;
- Interface Streamlit;
- Documentação técnica.

## 0.1.0 - Sprint 1

- Estruturação inicial do projeto;
- Criação do relatório simulado;
- Organização dos dados em JSON.

---

# 📋 Licença

Projeto acadêmico desenvolvido para o Challenge Sprint FIAP em parceria com a Dasa/Genera.

Uso exclusivamente educacional.
