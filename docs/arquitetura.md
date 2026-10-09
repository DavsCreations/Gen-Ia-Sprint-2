# Arquitetura da Solução — GenIA

Versão final (Sprint 4). A arquitetura da Sprint 2 — relatório em JSON, chunks, embeddings, ChromaDB e busca semântica — continua sendo o núcleo. Em volta dela entraram a geração por LLM, a orquestração multiagente, a validação das respostas, o registro de auditoria, a API e a interface web.

## 1. Visão geral

```text
┌───────────────────────── Navegador (desktop e celular) ─────────────────────────┐
│  Next.js + ReUI + Spell UI                                                       │
│  Painel · Conversa · Monitoramento · Privacidade                                 │
└──────────────────────────────────────┬───────────────────────────────────────────┘
                                       │ /api/*  (repasse pelo servidor do front-end)
┌──────────────────────────────────────▼───────────────────────────────────────────┐
│  API FastAPI (app/api.py)                                                        │
│  consentimento · limite de uso · token de operador                               │
│                                                                                  │
│  ┌──────────── Orquestração multiagente (app/agentes.py) ─────────────┐          │
│  │  1 Triagem ──► 2 Recuperador ──► 3 Redator ──► 4 Auditor           │          │
│  │  mascara dados   busca híbrida    LLM restrito   valida; reprova,  │          │
│  │  classifica      decide cobertura ao contexto    pede reescrita ou │          │
│  │  intenção                                        usa a reserva     │          │
│  └────────┬──────────────┬───────────────┬──────────────┬─────────────┘          │
│           │              │               │              │                        │
│   intencao.py         rag.py          llm.py       validador.py                  │
│   privacidade.py   (ChromaDB +     (Groq, Gemini,  (embeddings locais            │
│   (scikit-learn)    TF-IDF)         Ollama)         + regras)                    │
│                                                                                  │
│  Registro de auditoria (app/auditoria.py) ── SQLite ou Postgres + log JSON       │
│  Pipeline de ingestão monitorado (app/pipeline.py)                               │
└──────────────────────────────────────────────────────────────────────────────────┘
        ▲                                                   ▲
        │ data/relatorio_exemplo.json                       │ GitHub Actions
        │ data/glossario.json · data/intencoes.json         │ CI · avaliação · monitoramento · deploy
```

## 2. Fluxo de uma pergunta

| # | Agente | O que faz | Pode encerrar o fluxo? |
|---|---|---|---|
| 1 | **Triagem** | Mascara dados pessoais. Aplica as regras de segurança (injeção de instruções, conselho médico). Classifica a intenção com scikit-learn | Sim: bloqueia injeção, recusa conselho médico, responde saudação |
| 2 | **Recuperador** | Busca os três trechos mais relevantes e decide se o relatório cobre a pergunta | Sim: recusa quando não há cobertura |
| 3 | **Redator** | Escreve a resposta com o LLM usando só os trechos recuperados, no nível de linguagem pedido | Sim: declara que o relatório não trata do tema |
| 4 | **Auditor** | Roda as sete checagens. Reprovou: devolve os motivos ao Redator para uma reescrita. Reprovou de novo: usa a resposta de reserva | Sim: retém a resposta se nem a reserva passar |

Cada agente registra a decisão que tomou e o tempo gasto. Esse rastro volta junto com a resposta (explicabilidade) e é gravado no registro de auditoria (logging).

Os papéis são separados de propósito: quem escreve não é quem aprova. O Redator é o único componente não determinístico; Triagem, Recuperador e Auditor produzem sempre o mesmo resultado para a mesma entrada.

## 3. Componentes

### 3.1 Dados — `app/data_loader.py`

Lê o relatório, valida a estrutura e gera os chunks. Cada chunk tem um identificador estável (por exemplo `saude:diabetes-tipo-2`), que é o que aparece nas citações. A validação acusa campo ausente, campo desconhecido e percentuais que não somam 100: foi o tipo de checagem que teria apanhado o defeito da Sprint 2, em que uma chave escrita com acento fazia os percentuais de ancestralidade sumirem sem erro algum.

A identificação do paciente não é indexada.

### 3.2 Recuperação — `app/rag.py`

Busca híbrida:

- **Semântica:** embeddings multilíngues (`paraphrase-multilingual-MiniLM-L12-v2`, via ONNX) armazenados no ChromaDB. Cada chunk é indexado inteiro e também em passagens curtas, todas apontando para o chunk de origem.
- **Lexical:** TF-IDF (scikit-learn) sobre o texto do chunk mais um glossário de termos leigos (`data/glossario.json`), para que "leite" encontre "intolerância à lactose".

Pontuação final = similaridade semântica + 0,5 × similaridade lexical. Modelo e base ficam em cache no processo, e os vetores do relatório também em disco, o que reduz a subida da API de cerca de 14 para 2 segundos.

### 3.3 Intenção — `app/intencao.py`

Duas camadas: regras para o que é segurança, e um classificador (regressão logística sobre os embeddings da pergunta) treinado com `data/intencoes.json` para o restante. O classificador só decide sozinho quando está muito seguro; nos outros casos a pergunta segue e é o Recuperador que decide.

### 3.4 Geração — `app/llm.py`, `app/prompts.py`

Qualquer provedor com API compatível com a da OpenAI. Há predefinições para Groq e Gemini (nuvem) e Ollama (local). A versão publicada usa o Gemini 3.8 Flash. Temperatura 0 por padrão, para privilegiar consistência, e raciocínio do modelo desligado: ele consumia o limite de tokens e a resposta vinha cortada. Os prompts são versionados e a versão vai para o registro de cada resposta.

Sem provedor configurado, o sistema opera no **modo extrativo**: responde com frases do próprio relatório. É também a rede de segurança do Auditor e o modo usado na integração contínua, que assim não depende de chave nem de rede.

### 3.5 Validação — `app/validador.py`

Sete checagens, nenhuma delas com LLM: fundamentação por frase (similaridade com as passagens do contexto), números, citações, segurança, níveis, tamanho e legibilidade. Detalhes e resultados em `docs/avaliacao.md`.

### 3.6 Auditoria e privacidade — `app/auditoria.py`, `app/privacidade.py`

Registro estruturado em banco de dados (SQLite local, Postgres gerenciado no deploy) e em log JSON; pseudonimização da sessão; mascaramento de dados pessoais; exportação, exclusão e retenção. Política completa em `docs/governanca.md`.

### 3.7 Pipeline de ingestão — `app/pipeline.py`

Sete etapas monitoradas: carregar, validar estrutura, criar chunks, indexar, treinar o classificador, aquecer o validador e fazer uma busca de verificação. Falhou uma etapa, o pipeline para, registra a falha e devolve código de saída 1.

### 3.8 API — `app/api.py`

| Rota | Função |
|---|---|
| `GET /api/saude` | Situação do serviço e da ingestão |
| `GET /api/relatorio` | Dados do relatório para o painel, sem a identificação do paciente |
| `GET`/`POST /api/consentimento` | Consulta e registra o aceite do termo |
| `POST /api/perguntar` | Pergunta ao agente (exige consentimento) |
| `GET /api/resumo` | Resumo automático (exige consentimento) |
| `POST /api/feedback` | Avaliação útil / não útil |
| `GET`/`DELETE /api/meus-dados` | Exportação e eliminação dos dados da sessão |
| `GET /api/interacoes/{id}` | Registro de auditoria de uma interação da própria sessão |
| `GET /api/monitoramento` | Indicadores, execuções e eventos |
| `POST /api/pipeline/ingestao` | Reexecuta a ingestão (exige token de operador) |
| `GET /api/avaliacao` | Resultados da última avaliação |

### 3.9 Interface — `web/`

Next.js 16 com componentes de três fontes: shadcn/ui (base), **ReUI** (linha do tempo dos agentes, alertas, selos) e **Spell UI** (revelação do título, texto com brilho no carregamento, indicador de espera, botão de copiar). Quatro telas:

| Tela | Conteúdo |
|---|---|
| Painel | Resumo automático, composição de ancestralidade, cartões de saúde e bem-estar com nível de risco, alternância entre linguagem simples e técnica |
| Conversa | Perguntas ao agente; cada resposta com fontes, selo do Auditor e o painel "Como cheguei a esta resposta" |
| Monitoramento | Situação do serviço, indicadores, execuções de pipeline etapa a etapa, últimas interações (só metadados), eventos |
| Privacidade | Consentimento, exportação e exclusão dos dados, resumo da política, critérios de qualidade |

A interface é responsiva, tem navegação inferior no celular e um manifesto de aplicativo web, que permite instalá-la na tela inicial.

O navegador nunca fala direto com a API: o servidor do front-end repassa as chamadas (`web/app/api/[...caminho]/route.ts`). Assim a API não precisa ser pública: no deploy, só o serviço do front-end a alcança.

## 4. Decisões de projeto

| Decisão | Motivo |
|---|---|
| Manter ChromaDB e o relatório em JSON | Continuidade com as Sprints 1 e 2 |
| Embeddings via ONNX (fastembed) em vez de PyTorch | Mesma família de modelos, sem os gigabytes do `torch`; viabiliza o deploy |
| Embedding multilíngue | O original era treinado em inglês; a avaliação mostrou o ganho em português |
| Busca híbrida com glossário | Usuários perguntam em linguagem leiga; o relatório está em linguagem técnica |
| Auditor sem LLM | Parecer reproduzível e auditável; não dobra o custo nem a latência |
| Regras para segurança, modelo para o resto | Um classificador treinado com poucos exemplos não é base para decisão de segurança |
| Modo extrativo | Funciona sem chave, serve de reserva e torna a integração contínua determinística |
| API em Python e interface em Next.js | Aproveita o ecossistema de IA do Python e os componentes ReUI/Spell UI do React |
| SQLite local e Postgres no deploy | Localmente não exige serviço externo. No deploy a API roda em várias instâncias, e o primeiro teste em produção mostrou o aceite do termo se perdendo entre elas |

## 5. Limitações

- Um único relatório, simulado e igual para todos os visitantes; não há autenticação.
- A API usa cerca de 0,8 GB de memória (modelo de embeddings e runtime ONNX), o que exclui hospedagens gratuitas de 512 MB.
- Na execução local o registro é um arquivo SQLite; para rodar mais de uma instância da API é preciso definir `DATABASE_URL`.
- Não há histórico de conversa: cada pergunta é respondida de forma independente (o que também reduz o dado enviado ao LLM).
- Não há leitura de PDF: o relatório entra em JSON estruturado, como definido na Sprint 1.
