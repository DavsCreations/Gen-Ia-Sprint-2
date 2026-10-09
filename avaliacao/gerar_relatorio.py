"""
Gera docs/avaliacao.md a partir dos arquivos em avaliacao/resultados/.

O relatório é sempre regenerado a partir dos números medidos: nenhum valor é digitado à mão.
Uso: python -m avaliacao.gerar_relatorio
"""
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import RAIZ

DIR_RESULTADOS = Path(__file__).parent / "resultados"
DESTINO = RAIZ / "docs" / "avaliacao.md"
ARQUIVO_ANTES = "antes_dos_ajustes.json"
ARQUIVO_EXTRATIVO = "extrativo.json"

NOMES_TIPO = {
    "direta": "Pergunta direta", "parafrase": "Paráfrase", "leiga": "Linguagem leiga",
    "tema_ausente": "Tema de saúde ausente do relatório", "fora_escopo": "Fora do escopo",
    "conselho_medico": "Pedido de conselho médico", "injecao": "Injeção de instruções", "saudacao": "Saudação",
}
NOMES_CHECAGEM = {
    "fundamentacao": "fundamentação", "numeros": "números", "citacoes": "citações",
    "seguranca": "segurança", "niveis": "níveis", "tamanho": "tamanho",
}


def pct(valor: Optional[float]) -> str:
    return "—" if valor is None else f"{valor * 100:.1f}%".replace(".", ",")


def num(valor: Optional[float], casas: int = 3) -> str:
    return "—" if valor is None else f"{valor:.{casas}f}".replace(".", ",")


def tabela(cabecalho: List[str], linhas: List[List[Any]]) -> str:
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join("---" for _ in cabecalho) + "|"]
    saida += ["| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas]
    return "\n".join(saida)


def carregar(nome: str) -> Optional[Dict[str, Any]]:
    caminho = DIR_RESULTADOS / nome
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else None


def acuracia_nas_originais(resultado: Dict[str, Any]) -> float:
    """Acurácia de status só nas partições que já existiam antes dos ajustes."""
    linhas = [l for l in resultado["pipeline"]["detalhe"] if l["particao"] in ("calibracao", "teste")]
    return sum(l["status_correto"] for l in linhas) / len(linhas)


def respondidas_nas_originais(resultado: Dict[str, Any], tipos: tuple) -> int:
    """Quantas perguntas desses tipos receberam resposta, nas partições anteriores aos ajustes."""
    return sum(
        1 for l in resultado["pipeline"]["detalhe"]
        if l["particao"] in ("calibracao", "teste") and l["tipo"] in tipos and l["status"] == "respondida"
    )


def secao_resumo(antes: Optional[Dict[str, Any]], atual: Dict[str, Any]) -> str:
    final, original = atual["recuperacao"][-1], atual["recuperacao"][0]
    linhas = [
        ["Recuperação: trecho certo em 1º lugar", pct(original["acerto_top1"]) + " (Sprint 2)", pct(final["acerto_top1"])],
        ["Recuperação: trecho certo entre os 3 primeiros", pct(original["acerto_top3"]) + " (Sprint 2)", pct(final["acerto_top3"])],
    ]
    if antes:
        sensiveis = ("conselho_medico", "injecao")
        linhas += [
            ["Comportamento correto ponta a ponta (54 perguntas originais)", pct(antes["pipeline"]["acuracia_status"]), pct(acuracia_nas_originais(atual))],
            ["Pedidos de conselho médico ou injeção respondidos indevidamente", len(antes["pipeline"]["vazamentos"]),
             sum(1 for l in atual["pipeline"]["detalhe"] if l["tipo"] in sensiveis and l["status"] == "respondida")],
            ["Perguntas sem cobertura respondidas indevidamente (54 originais)", respondidas_nas_originais(antes, ("tema_ausente", "fora_escopo")),
             respondidas_nas_originais(atual, ("tema_ausente", "fora_escopo"))],
            ["Classificador de intenção (acurácia, validação cruzada)", pct(antes["intencao"]["validacao_cruzada"]["acuracia"]),
             pct(atual["intencao"]["validacao_cruzada"]["acuracia"])],
            ["Defeitos detectados pelo validador", f"{antes['validador']['defeitos_detectados']} de {antes['validador']['total_com_defeito']}",
             f"{atual['validador']['defeitos_detectados']} de {atual['validador']['total_com_defeito']}"],
        ]
    verificacao = atual["pipeline"]["acuracia_por_particao"].get("verificacao")
    texto = tabela(["Indicador", "Antes dos ajustes", "Versão final"], linhas)
    if verificacao is not None:
        total = sum(1 for l in atual["pipeline"]["detalhe"] if l["particao"] == "verificacao")
        texto += (
            f"\n\nNa partição de **verificação** ({total} perguntas escritas depois dos ajustes e nunca usadas "
            f"para ajustar o sistema), o comportamento foi correto em **{pct(verificacao)}** dos casos."
        )
    return texto


def secao_recuperacao(atual: Dict[str, Any]) -> str:
    linhas = [
        [c["configuracao"], pct(c["acerto_top1"]), pct(c["acerto_top3"]), num(c["mrr"]), num(c["separacao_auc"])]
        for c in atual["recuperacao"]
    ]
    texto = tabela(["Configuração", "Acerto em 1º", "Acerto nos 3 primeiros", "MRR", "Separação (AUC)"], linhas)
    final = atual["recuperacao"][-1]
    por_tipo = ", ".join(f"{NOMES_TIPO[t].lower()} {pct(v)}" for t, v in final["acerto_top1_por_tipo"].items())
    texto += f"\n\nAcerto em 1º lugar da configuração final por tipo de pergunta: {por_tipo}."
    if final["erros_top1"]:
        texto += "\n\nPerguntas em que o trecho esperado não ficou em 1º lugar na configuração final:\n\n"
        texto += "\n".join(f"- \"{e['pergunta']}\" — esperado `{e['esperado']}`, obtido `{e['obtido'][0]}`" for e in final["erros_top1"])
    return texto


def secao_escopo(atual: Dict[str, Any]) -> str:
    limiar = atual["limiar"]
    linhas = []
    for particao in limiar["apenas_limiar"]:
        so, regra = limiar["apenas_limiar"][particao], limiar["limiar_e_ancora_lexical"][particao]
        linhas.append([
            particao, f"{so['no_escopo']} / {so['sem_cobertura']}",
            f"{so['falsas_recusas']} / {so['respostas_indevidas']}", pct(so["acuracia_balanceada"]),
            f"{regra['falsas_recusas']} / {regra['respostas_indevidas']}", pct(regra["acuracia_balanceada"]),
        ])
    texto = tabela(
        ["Partição", "No escopo / sem cobertura", "Só limiar: falsas recusas / respostas indevidas", "Só limiar: acurácia balanceada",
         "Limiar + âncora: falsas recusas / respostas indevidas", "Limiar + âncora: acurácia balanceada"], linhas)
    texto += (
        f"\n\nO limiar em uso é **{num(limiar['limiar_em_uso'], 2)}**. Na partição de calibração, qualquer valor entre "
        f"{num(limiar['faixa_equivalente'][0], 2)} e {num(limiar['faixa_equivalente'][1], 2)} dá o mesmo resultado. "
        f"A menor pontuação de uma pergunta no escopo foi {num(limiar['pontuacoes']['no_escopo_minima'], 2)} e a maior de uma "
        f"pergunta sem cobertura foi {num(limiar['pontuacoes']['sem_cobertura_maxima'], 2)}: as duas faixas se sobrepõem, "
        "então nenhum limiar sozinho separa todos os casos."
    )
    if "peso_lexical" in atual:
        particoes = [p for p in atual["peso_lexical"][0] if p not in ("peso", "em_uso")]
        linhas = [
            [num(x["peso"], 2) + (" (em uso)" if x["em_uso"] else "")]
            + [f"{pct(x[p]['acerto_top1'])} / {num(x[p]['separacao_auc'])}" for p in particoes]
            for x in atual["peso_lexical"]
        ]
        texto += "\n\n**Peso da busca lexical** (acerto em 1º lugar / separação AUC, por partição):\n\n"
        texto += tabela(["Peso"] + particoes, linhas)
    return texto


def secao_intencao(atual: Dict[str, Any]) -> str:
    i = atual["intencao"]
    cv, original, externo = i["validacao_cruzada"], i["validacao_cruzada_classificador_original"], i["conjunto_avaliacao"]
    texto = tabela(
        ["Classificador", "Acurácia", "F1 macro"],
        [[f"Original — {original['descricao']}", pct(original["acuracia"]), num(original["f1_macro"])],
         ["Em uso — regressão logística sobre embeddings multilíngues", pct(cv["acuracia"]), num(cv["f1_macro"])]],
    )
    texto += f"\n\nValidação cruzada estratificada em 5 partes sobre {i['exemplos_de_treino']} exemplos de treino.\n\n"
    texto += "Matriz de confusão do classificador em uso (linhas: classe real; colunas: classe prevista):\n\n"
    texto += tabela([""] + cv["classes"], [[c] + linha for c, linha in zip(cv["classes"], cv["matriz_confusao"])])
    texto += (
        f"\n\nNo conjunto de avaliação ({externo['perguntas']} perguntas que o classificador nunca viu), a acurácia foi "
        f"**{pct(externo['acuracia'])}** (F1 macro {num(externo['f1_macro'])})."
    )
    if externo["erros"]:
        texto += " Erros:\n\n" + "\n".join(
            f"- \"{e['pergunta']}\" — esperado `{e['esperado']}`, previsto `{e['obtido']}`" for e in externo["erros"])
    inj, med = i["regras_de_injecao"], i["regras_de_conselho_medico"]
    texto += "\n\n**Regras determinísticas de segurança** (aplicadas antes do classificador):\n\n"
    texto += tabela(
        ["Regra", "Detectadas", "Falsos alarmes"],
        [["Injeção de instruções", f"{inj['detectadas']} de {inj['total']}", len(inj["falsos_alarmes"])],
         ["Pedido de conselho médico", f"{med['detectadas']} de {med['total']}", len(med["falsos_alarmes"])]],
    )
    return texto


def secao_validador(atual: Dict[str, Any]) -> str:
    v = atual["validador"]
    texto = (
        f"{v['casos']} respostas candidatas escritas à mão: {v['total_corretas']} corretas e {v['total_com_defeito']} com um defeito "
        f"conhecido. O validador detectou **{v['defeitos_detectados']} de {v['total_com_defeito']}** defeitos e reprovou "
        f"indevidamente **{v['falsas_reprovacoes']} de {v['total_corretas']}** respostas corretas.\n\n"
    )
    linhas = [
        [d["defeito"], "reprovada" if d["obtido"] == "reprovar" else "**aprovada (falha do validador)**",
         ", ".join(NOMES_CHECAGEM.get(f, f) for f in d["falhas"]) or "—"]
        for d in v["detalhe"] if d["esperado"] == "reprovar"
    ]
    texto += tabela(["Defeito inserido", "Decisão", "Checagens que reprovaram"], linhas)
    texto += f"\n\n**Sensibilidade ao limiar de apoio por frase** (em uso: {num(v['limiar_em_uso'], 2)}):\n\n"
    texto += tabela(
        ["Limiar", "Defeitos detectados", "Respostas corretas reprovadas"],
        [[num(c["limiar"], 2), f"{c['defeitos_detectados']} de {v['total_com_defeito']}", c["falsas_reprovacoes"]] for c in v["curva_limiar"]],
    )
    return texto


def secao_pipeline(atual: Dict[str, Any]) -> str:
    p = atual["pipeline"]
    contagem: Dict[str, int] = {}
    for linha in p["detalhe"]:
        contagem[linha["tipo"]] = contagem.get(linha["tipo"], 0) + 1
    texto = tabela(
        ["Tipo de pergunta", "Perguntas", "Comportamento correto"],
        [[NOMES_TIPO[t], contagem[t], pct(v)] for t, v in p["acuracia_por_tipo"].items()] + [["**Total**", p["perguntas"], f"**{pct(p['acuracia_status'])}**"]],
    )
    texto += "\n\nPor partição: " + ", ".join(f"{nome} {pct(v)}" for nome, v in p["acuracia_por_particao"].items()) + "."
    texto += f"\n\nLatência no modo `{atual['modo']}`: mediana {p['latencia_ms']['p50']} ms, percentil 95 {p['latencia_ms']['p95']} ms."
    falhas = [l for l in p["detalhe"] if not l["status_correto"]]
    if falhas:
        texto += "\n\n**Falhas restantes** (todas listadas, nenhuma omitida):\n\n"
        texto += "\n".join(f"- \"{l['pergunta']}\" ({NOMES_TIPO[l['tipo']].lower()}, {l['particao']}) — obtido `{l['status']}`" for l in falhas)
    return texto


def flesch_mediano(resultado: Dict[str, Any]) -> Optional[float]:
    valores = [l["flesch"] for l in resultado["pipeline"]["detalhe"] if l["flesch"] is not None]
    return statistics.median(valores) if valores else None


def secao_geracao(resultados: List[Dict[str, Any]]) -> str:
    linhas, consistencia = [], []
    for r in resultados:
        g, c = r["pipeline"]["respondidas"], r["consistencia"]
        linhas.append([
            f"`{r['modo']}`", g["total"], pct(g["fonte_correta"]), pct(g["fatos_presentes"]), num(g["apoio_medio"]),
            g["reprovadas_na_primeira_versao"], g["uso_fallback"], num(flesch_mediano(r), 1),
        ])
        rep = c["repeticao"]
        consistencia.append([
            f"`{r['modo']}`", "—" if c["temperatura"] is None else num(c["temperatura"], 1),
            f"{rep['total']} × {c['repeticoes_por_pergunta']}", num(rep["similaridade_media"]), num(rep["similaridade_minima"]),
            f"{rep['perguntas_com_resposta_identica']} de {rep['total']}", f"{rep['perguntas_com_mesmas_fontes']} de {rep['total']}",
            num(c["parafrases"]["similaridade_media"]),
        ])
    texto = "**Qualidade** das respostas dadas:\n\n"
    texto += tabela(
        ["Modo", "Respostas", "Fonte correta", "Fatos-chave presentes", "Apoio médio por frase",
         "Reprovadas na 1ª versão", "Trocadas pela extrativa", "Flesch (mediana)"], linhas)
    texto += "\n\n**Consistência**: a mesma pergunta repetida várias vezes e formulações diferentes do mesmo tema.\n\n"
    texto += tabela(
        ["Modo", "Temperatura", "Perguntas × repetições", "Similaridade média", "Similaridade mínima",
         "Respostas idênticas", "Mesmas fontes", "Similaridade entre paráfrases"], consistencia)
    if len(resultados) == 1 and resultados[0]["modo"] == "extrativo":
        texto += (
            "\n\n> **Pendente:** esta execução foi feita no modo extrativo (sem LLM), que é determinístico — por isso a "
            "similaridade entre repetições é 1,000. Para medir a qualidade e a consistência do modelo generativo, configure "
            "um provedor no `.env` e rode `python -m avaliacao.executar_avaliacao --rapido --pausa 2.5`: uma nova linha "
            "aparece nas duas tabelas acima."
        )
    return texto


def gerar() -> Path:
    antes, atual = carregar(ARQUIVO_ANTES), carregar(ARQUIVO_EXTRATIVO)
    if atual is None:
        raise SystemExit("Execute antes: python -m avaliacao.executar_avaliacao")
    outros = [
        json.loads(c.read_text(encoding="utf-8")) for c in sorted(DIR_RESULTADOS.glob("*.json"))
        if c.name not in (ARQUIVO_ANTES, ARQUIVO_EXTRATIVO)
    ]
    cfg = atual["configuracao"]
    tipos: Dict[str, int] = {}
    for linha in atual["pipeline"]["detalhe"]:
        tipos[linha["tipo"]] = tipos.get(linha["tipo"], 0) + 1

    partes = [
        "# Avaliação do Modelo e Validação das Respostas — GenIA",
        f"> Documento gerado por `python -m avaliacao.gerar_relatorio` a partir de `avaliacao/resultados/`. "
        f"Última execução: {atual['gerado_em']}. Não edite à mão: rode a avaliação de novo.",
        "## 1. Resumo",
        secao_resumo(antes, atual),
        "## 2. Como a avaliação foi feita",
        f"O conjunto de avaliação (`avaliacao/conjunto_avaliacao.json`) tem **{atual['perguntas']} perguntas**, cada uma com o "
        "comportamento esperado do sistema: qual trecho do relatório deve ser recuperado e qual deve ser o desfecho "
        "(responder, recusar por falta de cobertura, recusar conselho médico, bloquear).\n\n"
        + tabela(["Tipo de pergunta", "Quantidade"], [[NOMES_TIPO[t], n] for t, n in tipos.items()])
        + "\n\nAs perguntas estão divididas em três partições:\n\n"
        "- **calibração** — usada para escolher limiares;\n"
        "- **teste** — usada para medir; foi nela que apareceram as falhas que motivaram os ajustes da seção 9;\n"
        "- **verificação** — escrita depois dos ajustes e nunca usada para ajustar nada. É a estimativa mais honesta "
        "do comportamento em perguntas novas.\n\n"
        "Nenhuma pergunta de avaliação aparece nos exemplos de treino do classificador; o script confere isso a cada execução. "
        "O conjunto é pequeno e foi escrito pela própria equipe: os percentuais indicam tendência, não precisão estatística.",
        "## 3. Recuperação (busca no relatório)",
        "Cada linha acrescenta uma mudança à anterior. A primeira reproduz o código entregue na Sprint 2, incluindo o defeito "
        "que impedia os percentuais de ancestralidade de serem indexados. *MRR* é a média do inverso da posição do trecho "
        "correto. *Separação (AUC)* mede o quanto a pontuação distingue perguntas que o relatório cobre das que não cobre "
        "(1,0 = separação perfeita; 0,5 = acaso).",
        secao_recuperacao(atual),
        "## 4. Decisão de escopo: o relatório cobre a pergunta?",
        "Responder a uma pergunta que o relatório não cobre é o erro mais perigoso de um RAG neste domínio: o sistema "
        "entregaria o trecho mais parecido como se fosse a resposta. *Falsa recusa* é recusar uma pergunta que o relatório "
        "cobre; *resposta indevida* é responder uma que ele não cobre.",
        secao_escopo(atual),
        "## 5. Classificador de intenção (scikit-learn)",
        secao_intencao(atual),
        "## 6. Validador de respostas",
        "O validador (Agente Auditor) decide se uma resposta gerada pode ser exibida. Para saber se ele próprio é confiável, "
        "foi testado com respostas de qualidade conhecida (`avaliacao/casos_validador.json`).",
        secao_validador(atual),
        "## 7. Comportamento ponta a ponta",
        "Cada pergunta passa pelo fluxo completo (Triagem → Recuperador → Redator → Auditor) e o desfecho é comparado ao esperado.",
        secao_pipeline(atual),
        "## 8. Qualidade e consistência da geração",
        secao_geracao([atual] + outros),
        "## 9. Ajustes realizados a partir da avaliação",
        "| # | O que a avaliação mostrou | Ajuste | Onde |\n|---|---|---|---|\n"
        "| 1 | A chave `composição` (com acento) não existia no JSON: os percentuais de ancestralidade nunca eram indexados | "
        "Chave corrigida e validação de estrutura que acusa campos desconhecidos | `app/data_loader.py` |\n"
        "| 2 | O embedding `all-MiniLM-L6-v2`, treinado em inglês, errava perguntas em português leigo | "
        "Troca por `paraphrase-multilingual-MiniLM-L12-v2` | `app/config.py` |\n"
        "| 3 | Perguntas curtas não casavam com chunks longos | Indexação de passagens curtas apontando para o chunk pai | `app/rag.py` |\n"
        "| 4 | Termos leigos (\"leite\", \"glúten\") não encontravam o tema técnico | Busca híbrida: TF-IDF somado ao embedding, com glossário de termos leigos | `app/rag.py`, `data/glossario.json` |\n"
        "| 5 | Dois pedidos de conselho médico passaram pela triagem | Regras determinísticas para medicamento, dose, tratamento e sintomas | `app/intencao.py` |\n"
        "| 6 | O classificador de n-gramas de caracteres confundia intenções | Regressão logística sobre embeddings | `app/intencao.py` |\n"
        "| 7 | Temas de saúde ausentes eram respondidos com o trecho mais parecido | Exigência de âncora lexical além do limiar de pontuação | `app/agentes.py` |\n"
        "| 8 | O validador aprovou uma recomendação inventada e não distinguia \"alta\" de \"baixa\" predisposição | "
        "Limiar de apoio recalibrado, lista de substâncias ampliada e checagem de níveis | `app/validador.py` |\n"
        "| 9 | A cada pergunta o modelo era recarregado e a base reindexada | Modelo e base em cache no processo | `app/rag.py` |\n\n"
        "O resultado anterior aos ajustes 5 a 8 está preservado em `avaliacao/resultados/antes_dos_ajustes.json`.",
        "## 10. Limitações conhecidas",
        "- **Conjunto pequeno e de autoria própria.** As perguntas foram escritas pela equipe, não coletadas de usuários reais.\n"
        "- **Tema ausente com vocabulário do relatório.** \"Quanto custa o teste de ancestralidade?\" contém uma palavra do "
        "relatório e passa pela regra de cobertura no modo extrativo. No modo com LLM, a instrução de recusar temas ausentes é uma segunda barreira.\n"
        "- **Fundamentação por similaridade.** A checagem usa embeddings, que não detectam toda contradição lógica; "
        "as checagens de números e de níveis cobrem os casos mais graves, não todos.\n"
        "- **Legibilidade.** O índice de Flesch usa contagem aproximada de sílabas e serve como indicador, não como bloqueio. "
        "As respostas extrativas herdam o texto formal do relatório e ficam na faixa \"difícil\".\n"
        "- **Dados simulados.** Há um único relatório fictício; a avaliação não cobre variação entre relatórios.",
        "## 11. Como reproduzir",
        "```bash\npython -m avaliacao.executar_avaliacao            # avaliação completa no modo configurado\n"
        "python -m avaliacao.executar_avaliacao --rapido   # sem a comparação entre configurações\n"
        "python -m avaliacao.gerar_relatorio               # regenera este documento\n```\n\n"
        f"Configuração desta execução: embedding `{cfg['embedding']}`, {cfg['top_k']} trechos por pergunta, pontuação mínima "
        f"{num(cfg['score_minimo'], 2)}, peso lexical {num(cfg['peso_lexical'], 2)}, limiar de apoio por frase {num(cfg['limiar_frase'], 2)}, "
        f"prompt {cfg['prompt_versao']}.\n\n"
        "A avaliação devolve código de saída 1 quando um critério mínimo não é atingido, e por isso bloqueia a integração contínua:\n\n"
        + tabela(["Critério", "Mínimo", "Obtido", "Situação"],
                 [[f"`{c['criterio']}`", c["minimo"], c["obtido"], "atendido" if c["ok"] else "**não atendido**"] for c in atual["criterios"]]),
    ]
    DESTINO.write_text("\n\n".join(partes) + "\n", encoding="utf-8")
    return DESTINO


if __name__ == "__main__":
    print(f"Relatório gerado em {gerar().relative_to(RAIZ)}")
