# Operação: Monitoramento, Automações e Deploy — GenIA

Este documento cobre a parte de operação da Sprint 4: como os pipelines são monitorados, quais automações existem, como ler os registros e como publicar a aplicação.

## 1. Pipelines monitorados

| Pipeline | Quando roda | O que faz | Onde ver o resultado |
|---|---|---|---|
| **Ingestão** | Na subida da API; sob demanda (`python -m app.pipeline` ou pela página de monitoramento) | Carrega o relatório, valida a estrutura, cria os chunks, indexa, treina o classificador, aquece o validador e faz uma busca de verificação | Página Monitoramento → Execuções de pipeline |
| **Retenção** | Na subida da API | Apaga registros mais antigos que o prazo de retenção | Idem |
| **Resposta** (os quatro agentes) | A cada pergunta | Triagem → Recuperador → Redator → Auditor | Página Monitoramento → Últimas interações; painel "Como cheguei a esta resposta" |
| **Avaliação** | Na integração contínua, a cada push | Mede recuperação, escopo, intenção, validador e comportamento ponta a ponta | Aba Actions do GitHub; `docs/avaliacao.md` |

### 1.1 Ingestão, etapa por etapa

Saída real de `python -m app.pipeline`:

```text
[SUCESSO] carregar_relatorio                        0 ms  relatorio_exemplo.json lido
[SUCESSO] validar_estrutura                         0 ms  estrutura válida, sem avisos
[SUCESSO] criar_chunks                              0 ms  12 chunks
[SUCESSO] indexar_base_vetorial                  7281 ms  51 vetores, versão 936ead7b3430, modelo sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
[SUCESSO] treinar_classificador_de_intencao      3524 ms  classes: conselho_medico, fora_escopo, relatorio, saudacao
[SUCESSO] aquecer_validador                      3098 ms  150 passagens em cache
[SUCESSO] busca_de_verificacao                     29 ms  busca de verificação correta (pontuação 0.95)

Pipeline de ingestão: sucesso em 13933 ms
```

Essa é a primeira execução. Os vetores ficam em cache em disco, e as execuções seguintes levam cerca de 2 segundos.

A última etapa é uma verificação funcional: faz uma pergunta cuja resposta é conhecida e confere se o trecho certo volta em primeiro lugar. Uma base indexada sem erro, mas errada, é apanhada aqui.

### 1.2 Como uma falha aparece

Se uma etapa falha, o pipeline para, grava a execução como `falha` com o motivo e o comando termina com código de saída 1. A rota `/api/saude` passa a responder `degradado` e a página de monitoramento mostra o alerta com o erro. O teste `test_pipeline_registra_falha_quando_o_relatorio_e_invalido` reproduz o caso com um relatório sem as seções obrigatórias.

### 1.3 Indicadores em operação

A página **Monitoramento** (`docs/evidencias/05-monitoramento.png`) mostra, a partir do registro de auditoria:

- situação do serviço, versão, modelo em uso e versão do prompt e da base;
- perguntas processadas e quantas foram respondidas;
- latência mediana e percentil 95;
- respostas reprovadas pelo Auditor e quantas foram trocadas pela resposta de reserva;
- desfecho das perguntas (respondida, recusada, bloqueada) e intenção identificada;
- cada execução de pipeline, com as etapas;
- as últimas interações, só com metadados;
- eventos: consentimentos, exclusões de dados, uso da resposta de reserva.

A página se atualiza sozinha a cada 20 segundos.

## 2. Automações

| Automação | Arquivo | Gatilho | O que faz |
|---|---|---|---|
| Integração contínua | `.github/workflows/ci.yml` | Push e pull request | API: pipeline de ingestão, testes e avaliação com critérios mínimos. Front-end: lint e build |
| Monitoramento de produção | `.github/workflows/monitoramento.yml` | A cada 6 horas e sob demanda | Roda a verificação sintética; se falhar, abre ou atualiza uma issue; quando volta a passar, fecha |
| Deploy | `vercel.json` + `vercel deploy --prod` | Sob demanda, pela linha de comando | Constrói e publica juntos o front-end (`web/`) e a API (contêiner do `Dockerfile`). O build da API roda o pipeline de ingestão: relatório inválido derruba o build, não a produção |
| Verificação sintética | `automacao/verificar_producao.py` | Chamada pelo monitoramento; pode ser rodada à mão | Percorre saúde → consentimento → três perguntas → limpeza |

### 2.1 Verificação sintética

Simula um usuário e confere o comportamento esperado. Saída real contra o build de produção rodando localmente:

```text
[OK] saude: status ok, ingestão sucesso, geração extrativo
[OK] pergunta (respondida): obtido respondida, fontes ['saude:diabetes-tipo-2'], 0.1 s
[OK] pergunta (recusada_conselho_medico): obtido recusada_conselho_medico, fontes -, 0.0 s
[OK] pergunta (bloqueada): obtido bloqueada, fontes -, 0.0 s
[OK] limpeza: 3 interações de teste apagadas

Resultado: todas as verificações passaram
```

Ela verifica mais do que disponibilidade: confere que a fonte certa foi usada e que as salvaguardas continuam recusando o que devem recusar. No fim apaga os próprios dados, exercitando também a rota de eliminação.

### 2.2 Critérios mínimos na integração contínua

`python -m avaliacao.executar_avaliacao` termina com código 1 quando um critério não é atingido, e o job falha. Os critérios e os valores obtidos estão em `docs/avaliacao.md`, seção 11.

## 3. Como ler os registros

Cada interação gera uma linha JSON no log da aplicação (sem texto de pergunta ou resposta):

```json
{"log": "interacao", "em": "2026-10-09T14:08:57+00:00", "trace_id": "5dee4172cb3c4d70bcf6ffd70e5852ee",
 "sessao": "7ca2bbf26efab8f3", "tipo": "pergunta", "intencao": "relatorio", "status": "respondida",
 "provedor": "extrativo", "modelo": null, "prompt_versao": "v3", "base_versao": "936ead7b3430",
 "uso_fallback": false, "latencia_ms": 83}
```

O registro completo fica no banco (arquivo SQLite `var/auditoria.db` na execução local, Postgres no deploy) e pode ser consultado pelo identificador:

```bash
curl -H "X-Sessao: <sua sessão>" http://localhost:3000/api/interacoes/<trace_id>
```

A rota só devolve interações da própria sessão.

## 4. Execução local

Requisitos: Python 3.14 (versão em que o projeto foi desenvolvido e testado) e Node.js 20.9 ou superior.

```bash
# 1. API
python -m venv .venv
.\.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env              # opcional: preencha a chave do LLM
uvicorn app.api:app --port 8000

# 2. Front-end (em outro terminal)
cd web
npm install
npm run dev
```

Abra `http://localhost:3000`. Na primeira subida a API baixa o modelo de embeddings (cerca de 220 MB) e calcula os vetores do relatório; as seguintes são rápidas.

Outros comandos:

```bash
python -m app.main                               # conversa pelo terminal
python -m app.pipeline                           # pipeline de ingestão
python -m pytest -q                              # testes
python -m avaliacao.executar_avaliacao           # avaliação completa
python automacao/verificar_producao.py http://localhost:3000
```

## 5. Deploy

A aplicação está publicada na **Vercel**, em **https://genia-navy.vercel.app**, como um único projeto com dois serviços descritos em `vercel.json`:

| Serviço | Origem | Como roda | Exposição |
|---|---|---|---|
| `web` | `web/` (Next.js) | Funções e conteúdo estático da Vercel | Pública: recebe todo o tráfego |
| `api` | Raiz do repositório, pelo `Dockerfile` (FastAPI) | Contêiner sob demanda | **Privada**: só o serviço `web` a alcança, pelo vínculo declarado em `vercel.json` |

Os dois serviços são construídos e publicados juntos, na mesma versão. O navegador só fala com `web`; a rota `web/app/api/[...caminho]/route.ts` repassa as chamadas à API pelo endereço interno que a Vercel injeta em `API_URL`.

O registro de auditoria fica em um **Postgres gerenciado (Neon)**, criado pelo Marketplace da Vercel, que define a variável `DATABASE_URL` no projeto.

### 5.1 Como foi feito

```bash
vercel link --yes --project genia          # cria o projeto e reconhece os serviços do vercel.json
vercel env add GENIA_SAL production,preview --sensitive
vercel env add GENIA_TOKEN_OPERADOR production,preview
vercel integration add neon --name genia-auditoria   # exige aceitar os termos do Neon no navegador
vercel deploy --prod
python automacao/verificar_producao.py https://genia-navy.vercel.app
```

A chave do modelo de linguagem entra como segredo (`vercel env add GEMINI_API_KEY production,preview --sensitive`). A versão publicada usa o Gemini 3.8 Flash; sem chave, a aplicação funciona no modo extrativo.

O deploy é feito pela linha de comando. A integração automática com o GitHub não foi ligada porque o repositório pertence a outra conta; quem é dono do repositório pode conectá-lo com `vercel git connect`.

### 5.2 Por que o registro foi para um banco gerenciado

O primeiro deploy usava o arquivo SQLite dentro do contêiner da API. A verificação sintética falhou logo na primeira execução: a primeira pergunta foi respondida e a segunda recebeu erro 403. A Vercel tinha iniciado uma segunda instância da API, com um arquivo de registro vazio, e o aceite do termo estava na primeira.

Com o registro no Postgres, todas as instâncias enxergam os mesmos dados. O módulo `app/auditoria.py` usa Postgres quando `DATABASE_URL` existe e SQLite caso contrário, com as mesmas consultas.

### 5.3 Verificação em produção

Medido em 9 de outubro de 2026, contra https://genia-navy.vercel.app:

| Verificação | Resultado |
|---|---|
| Verificação sintética (`automacao/verificar_producao.py`), 3 execuções seguidas | Todas as etapas aprovadas |
| 20 perguntas simultâneas da mesma sessão | 20 respostas com sucesso, 20 interações registradas, aceite preservado, mesmo com instâncias novas atendendo |
| Primeira chamada com a API parada | Cerca de 8 a 10 segundos; as seguintes, cerca de 0,4 segundo por pergunta |
| `/api/saude` | `status: ok`, ingestão com sucesso, `registro: postgres` |
| Rota administrativa sem token de operador | Recusada (403) |
| Geração com o modelo real (`/api/saude`: `provedor: gemini`) | Respostas e resumo escritos pelo Gemini e aprovados pelo Auditor; cerca de 2 a 3 segundos por resposta |
| Fluxo completo das telas em navegador automatizado, em produção | Sem erros no console; sem rolagem horizontal no celular |

### 5.4 O que muda em produção

- **A primeira chamada depois de um período parado demora mais**, porque o contêiner da API precisa subir. O cache de vetores gravado no build mantém a ingestão em cerca de 2 segundos.
- **O banco fica em outra região.** O Neon está em `us-east-1`. O que vai para lá é o conteúdo do registro de auditoria: pseudônimo da sessão, metadados e, só com autorização, o texto das perguntas (ver `docs/governanca.md`, seção 2.5).
- **Memória:** a API usa cerca de 0,8 GB (medido localmente), dentro dos 2 GB do plano gratuito.
- **Teto de uso do LLM.** A aplicação gera no máximo 50 respostas ou resumos por dia com o modelo de linguagem, somando todas as sessões (variável `GENIA_LIMITE_LLM_DIA`). Acima disso responde no modo extrativo até o dia seguinte. O teto existe para limitar o custo da chave, já que o endereço é público; o limite de 20 perguntas por minuto por sessão, sozinho, não impediria alguém de abrir várias sessões.

### 5.5 Outra hospedagem

O `Dockerfile` serve em qualquer plataforma de contêiner com pelo menos 1 GB de memória. Nesse caso, publique `web/` separadamente e defina no front-end `API_URL` (endereço da API) e, se a API exigir autenticação, `API_TOKEN`. Se a plataforma rodar mais de uma instância da API, defina também `DATABASE_URL`.

### 5.6 O que ainda não foi verificado

- O monitoramento agendado (`.github/workflows/monitoramento.yml`) ainda não rodou: ele só é ativado depois do merge na `main` e da criação da variável de repositório `GENIA_URL`.
- O comportamento sob o limite de uso do plano gratuito do Gemini: se o provedor recusar por excesso de chamadas, a resposta cai na reserva extrativa (caminho coberto por teste), mas isso não foi provocado em produção.
