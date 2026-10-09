# Política de Governança de IA — GenIA

**Versão 2026-10 · Sprint 4 · Challenge FIAP / Dasa (Genera)**

Esta política descreve como o GenIA trata dados, registra o que faz e sustenta cada resposta que entrega. Ela foi escrita junto com o código: cada diretriz aponta para o arquivo que a implementa e, quando existe, para o teste que a verifica. Uma regra sem implementação é listada como lacuna na seção 9, não como controle.

> É um documento acadêmico, sobre uma solução que opera com um relatório genético **simulado**. Não substitui parecer jurídico. A seção 8 lista o que precisaria existir antes de qualquer uso com dados reais.

---

## 1. Escopo e papéis

| Item | Definição |
|---|---|
| O que o sistema faz | Explica ao titular o conteúdo do seu relatório genético, em linguagem simples ou técnica, citando a fonte de cada afirmação |
| O que o sistema não faz | Diagnóstico, prescrição, indicação de exame ou tratamento, previsão de que a pessoa terá uma doença, decisão automatizada sobre o titular |
| Controlador (cenário real) | Dasa/Genera, que define a finalidade do tratamento |
| Operador (cenário real) | Quem hospeda a aplicação e, quando há LLM em nuvem, o provedor do modelo |
| Titular | A pessoa a quem o relatório se refere |
| Responsáveis nesta entrega | Grupo 62 — desenvolvimento, avaliação e manutenção desta política |

---

## 2. LGPD

### 2.1 Natureza dos dados

Dado genético é **dado pessoal sensível** (LGPD, art. 5º, II). As perguntas do titular também são sensíveis: "tenho risco de diabetes?" revela uma preocupação de saúde. O sistema trata as duas coisas com o mesmo cuidado.

### 2.2 Base legal e consentimento

O tratamento se apoia no **consentimento específico e destacado do titular** (art. 11, I).

| Diretriz | Como está implementada |
|---|---|
| Nada é processado sem aceite | A API recusa perguntas e resumos sem consentimento registrado (HTTP 403) — `app/api.py`, `exigir_consentimento`; teste `test_perguntar_exige_sessao_e_consentimento` |
| O termo informa finalidade, dados tratados, retenção e direitos (art. 9º) | Diálogo exibido antes do primeiro uso — `web/components/genia/sessao.tsx` |
| Consentimento granular | Guardar o **texto** das perguntas e respostas é uma opção separada, desligada por padrão. Sem ela, só metadados são gravados — teste `test_sem_autorizacao_o_texto_nao_e_gravado` |
| Revogação a qualquer momento (art. 8º, § 5º) | Página Privacidade: desligar a gravação de texto ou apagar tudo |
| Novo termo exige novo aceite | O aceite guarda a versão do termo; mudou a versão, o aceite anterior deixa de valer — `app/privacidade.py`, `VERSAO_TERMO` |

### 2.3 Princípios (art. 6º)

| Princípio | Aplicação no GenIA |
|---|---|
| Finalidade e adequação | Uso único: explicar o relatório ao próprio titular. Perguntas fora disso são recusadas |
| Necessidade (minimização) | A identificação do paciente não é indexada, não vai ao modelo de linguagem e não é enviada ao navegador. CPF, e-mail, telefone e datas digitados na pergunta são mascarados antes de qualquer processamento — `app/privacidade.py`; testes `test_dados_do_paciente_nao_sao_indexados`, `test_dado_pessoal_e_mascarado_antes_de_ir_ao_llm` |
| Livre acesso | O titular vê e exporta tudo o que o sistema guarda sobre a sua sessão |
| Qualidade dos dados | O pipeline de ingestão valida a estrutura do relatório antes de indexar e interrompe em caso de erro |
| Transparência | Toda resposta mostra fontes, etapas e verificações (seção 3) |
| Segurança | Seção 2.6 |
| Prevenção | Recusas determinísticas para conselho médico e injeção de instruções; auditoria de toda resposta gerada |
| Não discriminação | O sistema não classifica nem pontua pessoas e não compartilha dados com terceiros para seleção de risco |
| Responsabilização e prestação de contas | Registro de auditoria (seção 4), avaliação reproduzível (`docs/avaliacao.md`) e esta política |

### 2.4 Direitos do titular (art. 18)

| Direito | Como exercer | Implementação |
|---|---|---|
| Confirmação e acesso (I, II) | Privacidade → "Exportar meus dados" | `GET /api/meus-dados` |
| Portabilidade (V) | A exportação é um arquivo JSON estruturado | idem |
| Eliminação (VI) | Privacidade → "Apagar meus dados" | `DELETE /api/meus-dados` apaga interações, eventos e consentimento; teste `test_titular_exporta_e_apaga_os_proprios_dados` |
| Revogação do consentimento (IX) | Mesma ação de eliminação, ou desligar a gravação de texto | idem |
| Informação sobre compartilhamento (VII) | Seção 2.5 desta política | — |
| Correção (III) | **Não implementada**: o relatório é emitido pelo laboratório; a correção caberia ao controlador | Lacuna registrada na seção 9 |

### 2.5 Compartilhamento com o provedor do modelo de linguagem

O GenIA funciona em três modos, e o fluxo de dados muda em cada um:

| Modo | O que sai da aplicação |
|---|---|
| Extrativo (sem LLM) | Nada. A resposta é montada com frases do próprio relatório |
| LLM local (Ollama) | Nada. O modelo roda na mesma máquina |
| LLM em nuvem (Groq, Gemini) | A pergunta **já mascarada** e os trechos do relatório usados naquela resposta. Não vão: identificação do paciente, identificador de sessão, histórico de conversa |

No modo em nuvem há transferência internacional de dados (art. 33), porque os provedores processam fora do Brasil. Com dados simulados isso não gera risco ao titular. Com dados reais, seria obrigatório um contrato que garanta não retenção e não uso para treino — ou o modo local.

### 2.6 Segurança (art. 46)

| Medida | Implementação |
|---|---|
| Pseudonimização da sessão | O registro guarda um hash com sal do identificador, nunca o original — `pseudonimizar`; teste `test_pseudonimo_e_estavel_e_nao_expoe_a_sessao` |
| Isolamento entre sessões | Uma sessão não lê o registro de outra — teste `test_fluxo_completo_com_consentimento` |
| API fora do alcance direto do navegador | O front-end repassa as chamadas pelo próprio servidor; no deploy a API é um serviço privado, sem rota pública — `web/app/api/[...caminho]/route.ts` |
| Limite de uso | Perguntas por minuto limitadas por sessão — teste `test_limite_de_perguntas_por_minuto` |
| Operações administrativas | Reexecutar o pipeline exige token de operador — teste `test_reexecucao_do_pipeline_exige_token_de_operador` |
| Segredos | Chaves ficam em variáveis de ambiente; `.env` não é versionado |
| Telemetria de terceiros | Desativada no banco vetorial — `app/rag.py`, `criar_cliente_chroma` |

### 2.7 Retenção e eliminação (arts. 15 e 16)

Registros de auditoria são apagados automaticamente após **30 dias** (configurável). A rotina roda a cada subida da aplicação e registra a própria execução — `app/auditoria.py`, `aplicar_retencao`; teste `test_retencao_apaga_registros_antigos`.

---

## 3. Explicabilidade

**Diretriz:** nenhuma resposta sobre o relatório é entregue sem que o usuário possa ver de onde ela veio e por que foi aceita.

Cada resposta traz o painel **"Como cheguei a esta resposta"** (`docs/evidencias/03-conversa-explicabilidade.png`), com:

| Elemento | O que mostra |
|---|---|
| Explicação em linguagem natural | Como a pergunta foi classificada, quais trechos foram encontrados e como a resposta foi produzida |
| Etapas executadas | Os quatro agentes (Triagem, Recuperador, Redator, Auditor), a decisão de cada um e o tempo gasto |
| Trechos consultados | Cada trecho do relatório com a pontuação de relevância, decomposta em parte semântica e parte lexical, e se foi usado ou descartado |
| Citações | Cada afirmação da resposta aponta para o trecho que a sustenta |
| Verificações do Auditor | O resultado de cada checagem (seção 5.2) e, se houve, as versões reprovadas antes |
| Apoio por frase | Para cada frase da resposta, o quanto ela é sustentada pelo relatório |
| Proveniência | Modelo, versão do prompt, versão da base e identificador do registro de auditoria |

Três decisões de projeto sustentam isso:

1. **As checagens não usam LLM.** São regras e similaridade de embeddings calculada localmente. O mesmo texto recebe sempre o mesmo parecer, e o parecer pode ser reproduzido.
2. **O que é questão de segurança é decidido por regra, não por modelo estatístico.** Injeção de instruções e pedido de conselho médico são detectados por padrões que qualquer pessoa pode ler em `app/intencao.py`.
3. **Recusas também são explicadas.** Quando o sistema não responde, diz o motivo: tema ausente do relatório, pedido de conselho médico ou tentativa de manipulação.

**Decisão automatizada (art. 20):** o GenIA não toma decisão que afete os interesses do titular — não concede, nega nem classifica nada. Ainda assim, cada resposta carrega um identificador que permite a uma pessoa revisar exatamente o que aconteceu.

---

## 4. Logging

**Diretriz:** tudo o que o sistema faz deixa rastro suficiente para reconstruir o que aconteceu, e nada além do necessário é guardado.

### 4.1 O que é registrado

| Registro | Conteúdo | Onde |
|---|---|---|
| Interação | Identificador, pseudônimo da sessão, horário, intenção, desfecho, fontes e pontuações, resultado de cada checagem, etapas dos agentes, provedor, modelo, versão do prompt, modelo de embedding, versão da base, uso de resposta de reserva, latência | Tabela `interacoes` |
| Execução de pipeline | Pipeline, horário, duração, situação e o detalhe de cada etapa | Tabela `execucoes` |
| Evento | Consentimento, exclusão de dados, troca pela resposta de reserva | Tabela `eventos` |
| Consentimento | Pseudônimo, horário, versão do termo, opção de gravar texto | Tabela `consentimentos` |

Implementação em `app/auditoria.py`. Cada registro também sai como uma linha JSON no log da aplicação, que a plataforma de hospedagem coleta.

### 4.2 O que não é registrado

| Dado | Tratamento |
|---|---|
| Identificador original da sessão | Nunca gravado; só o pseudônimo |
| Dados pessoais digitados | Mascarados antes de chegar ao registro |
| Texto da pergunta e da resposta | Só com autorização expressa; nunca no log de aplicação, mesmo com autorização |
| Identificação do paciente | Não entra em nenhum registro |

A página de monitoramento mostra apenas agregados e metadados — teste `test_monitoramento_nao_expoe_texto_de_perguntas`.

### 4.3 Rastreabilidade

O identificador de cada interação liga quatro coisas: a resposta exibida, o registro de auditoria, a versão do prompt (`app/prompts.py`, com histórico de mudanças no próprio arquivo) e a versão da base, que muda sempre que o relatório ou o modelo de embedding mudam. Com esses quatro dados é possível dizer com qual instrução, sobre quais dados e por qual modelo uma resposta foi produzida.

---

## 5. Controles de qualidade da resposta

### 5.1 Antes de gerar

| Controle | O que faz |
|---|---|
| Triagem por regra | Bloqueia injeção de instruções e recusa pedidos de medicamento, dose, tratamento, exame ou interpretação de sintomas — sem acionar o modelo de linguagem |
| Decisão de cobertura | O sistema só responde se o relatório cobre a pergunta: pontuação mínima e uma palavra relevante em comum (ou similaridade semântica alta) |
| Contexto restrito | O modelo recebe apenas os trechos recuperados, com instrução de não usar conhecimento externo e de tratar o conteúdo como dado, não como ordem |

### 5.2 Depois de gerar — Agente Auditor

| Checagem | Reprova quando | Bloqueia? |
|---|---|---|
| Fundamentação | Alguma frase não tem apoio em um trecho do relatório | Sim |
| Números | Aparece um número que não está no relatório | Sim |
| Citações | Não há citação, ou cita fonte que não foi recuperada | Sim |
| Segurança | Há linguagem de diagnóstico, prescrição, dose ou medicamento | Sim |
| Níveis | Usa "alto", "baixo", "moderado" etc. em desacordo com o relatório | Sim |
| Tamanho | Passa do limite de palavras | Sim |
| Legibilidade | Índice de Flesch abaixo do alvo para linguagem simples | Não (informativa) |

Se a resposta do modelo é reprovada, ele recebe os motivos e reescreve uma vez. Se for reprovada de novo, ou se o provedor falhar, entra a **resposta de reserva**, montada só com frases do relatório. Se nem ela passar, o sistema retém a resposta e avisa. Testes: `test_auditor_reprova_e_redator_reescreve`, `test_duas_reprovacoes_levam_a_resposta_extrativa`, `test_falha_do_llm_leva_a_resposta_extrativa`.

---

## 6. Critérios de acompanhamento responsável

### 6.1 Critérios mínimos (bloqueiam a entrega)

A avaliação roda a cada alteração do código. Se um critério não é atingido, a integração contínua falha.

| Critério | Mínimo |
|---|---|
| Trecho correto entre os três primeiros | 90% |
| Comportamento correto ponta a ponta | 85% |
| Pedidos de conselho médico ou injeção respondidos | 0 |
| Defeitos conhecidos detectados pelo validador | 90% |
| Respostas corretas reprovadas indevidamente | no máximo 1 |

Os valores obtidos e a metodologia estão em `docs/avaliacao.md`.

### 6.2 Indicadores acompanhados em operação

| Indicador | Por que importa | Onde ver |
|---|---|---|
| Situação da ingestão | Uma base mal indexada compromete todas as respostas | Monitoramento |
| Desfecho das perguntas | Salto em recusas pode indicar relatório fora do padrão ou uso indevido | Monitoramento |
| Respostas reprovadas pelo Auditor | Mede o quanto o modelo desvia das regras | Monitoramento |
| Uso da resposta de reserva | Indica instabilidade do provedor ou do modelo | Monitoramento e eventos |
| Latência (mediana e percentil 95) | Experiência do usuário | Monitoramento |
| Avaliação do usuário (útil / não útil) | Sinal direto de qualidade percebida | Registro de auditoria |
| Verificação sintética agendada | Detecta indisponibilidade sem depender de reclamação | GitHub Actions (abre issue em caso de falha) |

### 6.3 Quando reavaliar

A avaliação completa deve ser refeita sempre que mudar o modelo de linguagem, o prompt (o que exige nova versão), o modelo de embedding, os limiares, ou a estrutura do relatório.

### 6.4 Resposta a incidentes

1. A verificação agendada ou um usuário reporta o problema; uma issue é aberta.
2. O identificador da interação permite reconstruir o caso pelo registro de auditoria.
3. Se o problema for uma resposta inadequada, o caso entra no conjunto de avaliação antes da correção, para não se repetir.
4. Em cenário real, incidente com dado pessoal seria comunicado à ANPD e aos titulares (art. 48).

---

## 7. Limites declarados ao usuário

O sistema informa, em toda resposta sobre saúde, que o conteúdo é informativo e não substitui avaliação profissional. O termo de consentimento e a página Privacidade repetem que não há diagnóstico. O painel inicial exibe os limites do próprio relatório.

---

## 8. O que falta para uso com dados reais

Esta entrega opera com um relatório fictício. Antes de qualquer dado real, seriam pré-requisitos:

| Pré-requisito | Situação |
|---|---|
| Autenticação do titular | Não existe. Hoje qualquer visitante vê o mesmo relatório simulado |
| Relatório de Impacto à Proteção de Dados (art. 38) | Não elaborado |
| Encarregado (art. 41) e canal de atendimento ao titular | Não definidos |
| Contrato com o provedor do modelo (não retenção, não treino) ou modelo local | Não aplicável a dados simulados |
| Criptografia em repouso e registro em banco gerenciado | O registro é um arquivo SQLite local |
| Controle de acesso à página de monitoramento | Hoje é aberta, por expor só agregados |
| Revisão por profissional de saúde do conteúdo e das mensagens | Não realizada |
| Teste com usuários reais e avaliação de vieses | Não realizado |

---

## 9. Lacunas e limitações conhecidas

- **Nomes próprios não são mascarados.** O mascaramento usa expressões regulares, que não reconhecem nomes.
- **Direito de correção não implementado** (seção 2.4).
- **A checagem de fundamentação usa similaridade semântica**, que não detecta toda contradição lógica. As checagens de números e de níveis cobrem os casos mais graves.
- **Tema ausente com vocabulário do relatório** pode passar pela decisão de cobertura no modo extrativo; a avaliação lista os casos.
- **O registro não sobrevive ao desligamento do contêiner da API** no deploy: o arquivo SQLite é efêmero. As linhas do log de aplicação permanecem na plataforma, mas consentimentos e interações recomeçam. Uso real exigiria um banco gerenciado.
- **A qualidade do modelo generativo ainda precisa ser medida com um provedor configurado**; ver seção 8 de `docs/avaliacao.md`.

---

## 10. Revisão desta política

A política tem a mesma versão do termo de consentimento (`2026-10`). Mudou o tratamento de dados, muda a versão — e o sistema volta a pedir o aceite.
