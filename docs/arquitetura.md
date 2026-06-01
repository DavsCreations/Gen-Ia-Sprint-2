# Arquitetura da Solução — GenIA

## 1. Visão Geral

O GenIA utiliza uma arquitetura baseada em **Retrieval-Augmented Generation (RAG)** para permitir consultas inteligentes sobre relatórios genéticos simulados.

Nesta Sprint, o foco foi implementar a camada de inteligência responsável por recuperar informações relevantes a partir de um relatório estruturado em JSON e apresentar respostas fundamentadas no conteúdo recuperado.

A solução combina:

- Processamento de dados em JSON;
- Segmentação textual em chunks;
- Geração de embeddings;
- Armazenamento em base vetorial;
- Busca semântica;
- Interface web para consulta.

---

## 2. Fluxo Geral da Arquitetura

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

## 3. Componentes da Solução

## 3.1 Relatório Genético Simulado

Arquivo:

```text
data/relatorio_exemplo.json
```

Esse arquivo representa um relatório genético fictício utilizado para testes acadêmicos.

Ele contém informações simuladas sobre:

- Ancestralidade;
- Predisposições genéticas;
- Bem-estar;
- Recomendações gerais;
- Avisos de caráter informativo.

O uso de dados simulados foi adotado para evitar exposição de informações reais e sensíveis de saúde.

---

## 3.2 Data Loader

Arquivo:

```text
app/data_loader.py
```

Responsabilidades:

- Ler o arquivo JSON;
- Carregar os dados do relatório;
- Separar as informações relevantes;
- Preparar os textos para o processo de chunking.

Principais funções:

```text
carregar_relatorio()
criar_chunks()
```

---

## 3.3 Chunking

O chunking é o processo de dividir o relatório em blocos menores de texto.

Essa etapa é necessária porque a busca semântica funciona melhor quando os dados estão organizados em trechos específicos.

Exemplo de chunk:

```text
Tema: Diabetes tipo 2
Resultado: Predisposição genética moderada
Explicação técnica: Foram identificadas variantes genéticas associadas ao metabolismo da glicose.
Explicação simples: O relatório indica que a pessoa pode ter uma chance um pouco maior de desenvolver diabetes tipo 2.
Recomendação: Manter alimentação equilibrada e acompanhamento médico preventivo.
```

Vantagens do chunking:

- Melhora a precisão da busca;
- Facilita a recuperação de contexto;
- Permite rastrear a fonte da resposta;
- Evita uso desnecessário do relatório inteiro.

---

## 3.4 Embeddings

Os chunks são transformados em vetores numéricos por meio de embeddings.

Modelo utilizado:

```text
all-MiniLM-L6-v2
```

Biblioteca utilizada:

```text
sentence-transformers
```

Os embeddings permitem que o sistema compare semanticamente a pergunta do usuário com os trechos do relatório.

Exemplo conceitual:

```text
Pergunta: Tenho risco de diabetes?
```

Essa pergunta é convertida em vetor e comparada com os vetores dos chunks armazenados.

O trecho semanticamente mais próximo é recuperado.

---

## 3.5 Base Vetorial

Banco vetorial utilizado:

```text
ChromaDB
```

A base vetorial armazena:

- ID do chunk;
- Texto do chunk;
- Embedding;
- Metadados.

Exemplo de metadado:

```json
{
  "fonte": "relatorio_exemplo.json",
  "chunk": 2
}
```

A presença dos metadados permite rastrear qual trecho foi utilizado para gerar a resposta.

---

## 3.6 Busca Semântica

A busca semântica ocorre quando o usuário realiza uma pergunta.

Fluxo:

```text
Pergunta do usuário
        ↓
Geração de embedding da pergunta
        ↓
Comparação com embeddings dos chunks
        ↓
Recuperação do chunk mais relevante
```

Diferente de uma busca por palavra-chave, a busca semântica considera o significado da pergunta.

Exemplo:

```text
"Pressão alta"
```

pode ser semanticamente relacionado a:

```text
"Hipertensão arterial"
```

mesmo que as palavras não sejam exatamente iguais.

---

## 3.7 Motor RAG

Arquivo principal:

```text
app/rag.py
```

Responsabilidades:

- Carregar o modelo de embeddings;
- Criar a base vetorial;
- Consultar o ChromaDB;
- Recuperar o contexto;
- Montar uma resposta formatada;
- Exibir fonte e chunk utilizado;
- Incluir aviso de segurança médica.

Funções principais:

```text
carregar_modelo()
preparar_base_vetorial()
buscar_contexto()
gerar_resposta_formatada()
```

---

## 3.8 Interface Web

Arquivo:

```text
app/interface.py
```

Tecnologia utilizada:

```text
Streamlit
```

A interface permite que o usuário:

- Digite uma pergunta;
- Consulte o relatório genético;
- Visualize a resposta;
- Leia o aviso de segurança;
- Interaja de forma mais amigável com o sistema.

---

## 4. Justificativa Técnica

A arquitetura RAG foi escolhida porque permite que o sistema responda perguntas com base em um contexto recuperado de uma fonte específica.

Isso reduz o risco de respostas inventadas, pois a resposta é fundamentada no trecho recuperado do relatório.

Benefícios da arquitetura:

- Maior rastreabilidade;
- Menor risco de alucinação;
- Respostas baseadas em fonte;
- Facilidade de auditoria;
- Adequação ao contexto sensível de saúde.

---

## 5. Decisões de Projeto

## 5.1 Uso de JSON

O JSON foi escolhido por ser simples, estruturado e adequado para representar relatórios simulados nesta etapa do projeto.

## 5.2 Uso de ChromaDB

O ChromaDB foi escolhido por ser uma base vetorial simples de usar, compatível com Python e adequada para protótipos acadêmicos.

## 5.3 Uso de Sentence Transformers

O modelo `all-MiniLM-L6-v2` foi escolhido por ser leve, rápido e suficiente para demonstrar busca semântica.

## 5.4 Uso de Streamlit

O Streamlit foi escolhido por permitir a criação rápida de uma interface web funcional para demonstração.

---

## 6. Limitações da Arquitetura Atual

A versão atual possui algumas limitações:

- Utiliza relatório simulado;
- Não processa PDF diretamente;
- Não realiza diagnóstico médico;
- Não usa dados reais de pacientes;
- Não possui autenticação;
- Não possui armazenamento seguro de usuários;
- Não substitui avaliação profissional.

Essas limitações são aceitáveis para o escopo da Sprint 2.

---

## 7. Possíveis Evoluções Futuras

Melhorias futuras possíveis:

- Upload de relatórios em PDF;
- Extração automática de dados do PDF;
- Persistência da base vetorial em disco;
- Interface com histórico de conversa;
- Autenticação de usuários;
- Melhor tratamento de perguntas fora do escopo;
- Integração com LLM para respostas mais naturais;
- Camada mais robusta de governança e privacidade.

---

## 8. Conclusão

A arquitetura desenvolvida demonstra os principais fundamentos de um sistema RAG aplicado à consulta de relatórios genéticos.

O GenIA recupera informações relevantes, utiliza busca semântica, apresenta respostas rastreáveis e mantém limites de segurança adequados ao contexto de saúde.

A solução atende ao objetivo da Sprint 2 ao implementar a camada de inteligência do projeto com foco em clareza, rastreabilidade, governança e viabilidade técnica.