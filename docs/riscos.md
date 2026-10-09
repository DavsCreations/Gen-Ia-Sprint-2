# Análise de Riscos — GenIA

Versão final (Sprint 4). Na Sprint 2 os riscos estavam listados com mitigações declaradas. Agora cada risco tem o controle que foi implementado, a evidência de que ele funciona e o risco que sobra.

Probabilidade e impacto são estimativas da equipe, considerando os controles em vigor.

## 1. Riscos de conteúdo

| # | Risco | Controle implementado | Evidência | Risco residual |
|---|---|---|---|---|
| 1 | **Alucinação**: a resposta afirma algo que não está no relatório | O Redator recebe só os trechos recuperados. O Auditor reprova frase sem apoio, número ausente do relatório e nível trocado. Duas reprovações levam à resposta de reserva | Validador detectou 12 de 12 defeitos inseridos, sem reprovar respostas corretas (`docs/avaliacao.md`, seção 6) | Médio: a fundamentação por similaridade não detecta toda contradição lógica |
| 2 | **Interpretação como diagnóstico** | Recusa por regra de pedidos de medicamento, dose, tratamento, exame e sintomas. Checagem de linguagem de diagnóstico e prescrição na resposta. Aviso em toda resposta | Nenhum dos 18 pedidos de conselho médico ou injeção foi respondido | Baixo |
| 3 | **Resposta sobre tema ausente**: o sistema entrega o trecho mais parecido | Decisão de cobertura (pontuação mínima e âncora lexical). Instrução ao LLM para declarar a ausência | Das 17 perguntas sem cobertura, 15 foram recusadas no modo extrativo (uma delas com a mensagem de conselho médico em vez da de falta de cobertura) e 2 foram respondidas indevidamente | Médio: os casos estão listados na avaliação, seção 7 |
| 4 | **Recuperação do trecho errado** | Embedding multilíngue, passagens curtas, busca lexical e glossário | Trecho certo em 1º lugar em 97,2% dos casos (33,3% na Sprint 2) | Baixo |
| 5 | **Injeção de instruções** | Regras determinísticas antes de qualquer chamada ao LLM. O prompt trata contexto e pergunta como dado | 8 de 8 tentativas bloqueadas, sem falsos alarmes | Médio: padrões novos de ataque exigem atualizar as regras |
| 6 | **Recusa indevida** de pergunta legítima | O classificador só recusa sozinho com confiança alta; no restante decide a cobertura | Nenhuma falsa recusa nas 36 perguntas no escopo | Baixo |
| 7 | **Inconsistência** entre respostas à mesma pergunta | Temperatura 0; Triagem, Recuperador e Auditor determinísticos | Modo extrativo: respostas idênticas em todas as repetições | A medir com LLM configurado |
| 8 | **Texto difícil para leigos** | Nível "linguagem simples" no prompt; índice de legibilidade em cada resposta | O indicador é exibido; as respostas extrativas ficam na faixa "difícil" | Médio no modo extrativo, que herda o texto do relatório |

## 2. Riscos de privacidade

| # | Risco | Controle implementado | Evidência | Risco residual |
|---|---|---|---|---|
| 9 | **Exposição de dado genético** | Dados simulados. Identificação do paciente fora do índice, do LLM e do navegador | `test_dados_do_paciente_nao_sao_indexados`, `test_relatorio_nao_expoe_identificacao_do_paciente` | Baixo nesta entrega. Alto com dados reais sem autenticação |
| 10 | **Dado pessoal digitado na pergunta** chega ao LLM ou ao registro | Mascaramento de CPF, e-mail, telefone e datas antes de qualquer processamento | `test_dado_pessoal_e_mascarado_antes_de_ir_ao_llm` | Médio: nomes próprios não são detectados |
| 11 | **Registro vira base de dados sensíveis** | Texto só com autorização; sessão pseudonimizada; retenção de 30 dias; exclusão pelo titular | `test_sem_autorizacao_o_texto_nao_e_gravado`, `test_retencao_apaga_registros_antigos` | Baixo |
| 12 | **Envio de dados ao provedor do LLM** | Só a pergunta mascarada e os trechos usados; modo local e modo extrativo disponíveis | Política de governança, seção 2.5 | Baixo com dados simulados. Exige contrato ou modelo local com dados reais |
| 13 | **Página de monitoramento expõe conteúdo** | A rota devolve só agregados e metadados | `test_monitoramento_nao_expoe_texto_de_perguntas` | Baixo |

## 3. Riscos de operação

| # | Risco | Controle implementado | Evidência | Risco residual |
|---|---|---|---|---|
| 14 | **Provedor do LLM indisponível** ou no limite de uso | Nova tentativa automática; depois, resposta de reserva; evento registrado | `test_falha_do_llm_leva_a_resposta_extrativa`, `test_fallback_gera_evento_de_monitoramento` | Baixo: o serviço degrada, não cai |
| 15 | **Relatório malformado** indexado em silêncio | Validação de estrutura no pipeline; a ingestão para e registra a falha | `test_pipeline_registra_falha_quando_o_relatorio_e_invalido` | Baixo |
| 16 | **Regressão de qualidade** após uma mudança | Testes e avaliação com critérios mínimos na integração contínua | `.github/workflows/ci.yml` | Baixo |
| 17 | **Serviço fora do ar sem ninguém notar** | Verificação sintética agendada que abre uma issue | `.github/workflows/monitoramento.yml`, `automacao/verificar_producao.py` | Médio: intervalo de 6 horas entre verificações |
| 18 | **Abuso da API** consome a cota do LLM | Limite de perguntas por sessão; API acessível só pelo front-end | `test_limite_de_perguntas_por_minuto` | Médio: o limite é por sessão, e uma sessão nova é fácil de criar |
| 19 | **Perda do registro** em hospedagem com disco efêmero | Cada registro também sai no log da aplicação, coletado pela plataforma | `app/auditoria.py`, `_emitir` | Médio: o banco em si recomeça a cada reinício |

## 4. Riscos que esta entrega não trata

- **Viés e adequação cultural** das explicações: não houve teste com usuários reais.
- **Validação clínica** do conteúdo: nenhum profissional de saúde revisou as mensagens.
- **Variação entre relatórios**: há um único relatório simulado.

A seção 8 de `docs/governanca.md` lista o que seria pré-requisito para uso com dados reais.
