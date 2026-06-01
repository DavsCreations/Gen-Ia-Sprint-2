# Análise de Riscos — GenIA

## 1. Objetivo

Este documento apresenta os principais riscos identificados durante o desenvolvimento do GenIA.

---

## 2. Riscos Técnicos

### Risco 1 — Recuperação incorreta de contexto

Descrição:

A busca semântica pode recuperar um trecho que não represente exatamente a intenção do usuário.

Impacto:

Médio

Mitigação:

- Utilização de embeddings semânticos;
- Limitação do escopo do relatório;
- Exibição da fonte utilizada.

---

### Risco 2 — Dados insuficientes

Descrição:

O relatório pode não possuir informações suficientes para responder determinada pergunta.

Impacto:

Médio

Mitigação:

- Informar claramente a origem da resposta;
- Limitar respostas ao conteúdo disponível.

---

### Risco 3 — Hallucination

Descrição:

Sistemas de IA podem gerar respostas não fundamentadas.

Impacto:

Alto

Mitigação:

- Arquitetura RAG;
- Recuperação baseada em contexto;
- Uso exclusivo dos dados presentes no relatório.

---

## 3. Riscos de Negócio

### Risco 4 — Interpretação médica indevida

Descrição:

Usuários podem interpretar as respostas como diagnóstico médico.

Impacto:

Alto

Mitigação:

- Aviso obrigatório em todas as respostas;
- Restrição de escopo;
- Governança aplicada.

---

### Risco 5 — Uso de dados sensíveis

Descrição:

Relatórios genéticos representam dados sensíveis de saúde.

Impacto:

Alto

Mitigação:

- Uso de dados simulados;
- Não armazenamento de dados reais.

---

## 4. Classificação Geral

| Risco | Probabilidade | Impacto |
|---------|--------------|----------|
| Contexto incorreto | Média | Média |
| Dados insuficientes | Média | Média |
| Hallucination | Baixa | Alta |
| Interpretação médica | Média | Alta |
| Dados sensíveis | Baixa | Alta |

---

## 5. Conclusão

Os principais riscos identificados estão relacionados à interpretação de informações genéticas e à confiabilidade das respostas.

A utilização da arquitetura RAG reduz significativamente o risco de respostas sem fundamento e aumenta a rastreabilidade do sistema.