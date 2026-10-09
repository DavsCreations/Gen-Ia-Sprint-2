"""
Validação das respostas do GenIA (PLN).

Toda resposta gerada passa por estas checagens antes de chegar ao usuário:

- fundamentacao: cada frase precisa ter apoio semântico em algum trecho do contexto;
- numeros: todo número citado precisa existir no contexto (bloqueia percentuais inventados);
- citacoes: a resposta cita fontes, e só fontes que foram de fato recuperadas;
- seguranca: sem diagnóstico, prescrição, dose ou medicamento fora do contexto;
- niveis: qualificadores de resultado (alto, baixo, moderado...) conferem com o contexto;
- tamanho: dentro do limite de palavras;
- legibilidade: índice de Flesch adaptado ao português (informativa, não bloqueia).

As checagens são determinísticas ou baseadas em embeddings locais: nenhuma depende de LLM,
então o resultado é reproduzível e pode ser auditado.
"""
import re
from types import SimpleNamespace
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from app.prompts import AVISO_PADRAO
from app.rag import gerar_embeddings
from app.texto import dividir_frases, extrair_numeros, normalizar, tokenizar

# Calibrados com avaliacao/casos_validador.json — ver docs/avaliacao.md.
LIMIAR_FRASE = 0.50
MINIMO_FRASES_APOIADAS = 1.0
MAX_PALAVRAS = 160
MAX_PALAVRAS_RESUMO = 260
FLESCH_MINIMO_SIMPLES = 40.0

REGEX_CITACAO = re.compile(r"\[([a-z-]+:[a-z0-9-]+)\]")

FRASE_SEM_INFORMACAO = "O relatório não traz informações sobre esse tema."

# Frases de segurança que a resposta pode conter mesmo sem estarem no trecho recuperado.
FRASES_PERMITIDAS = [
    AVISO_PADRAO,
    FRASE_SEM_INFORMACAO,
    "Predisposição genética não é diagnóstico.",
    "Predisposição genética não significa que a pessoa terá a doença.",
    "Converse com um profissional de saúde para avaliar o seu caso.",
    "Hábitos de vida, ambiente e histórico familiar também influenciam a saúde.",
]

MEDICAMENTOS = {
    "metformina", "glibenclamida", "losartana", "captopril", "enalapril", "hidroclorotiazida",
    "atenolol", "anlodipino", "omeprazol", "sinvastatina", "atorvastatina", "ozempic",
    "semaglutida", "aspirina", "ibuprofeno", "dipirona", "paracetamol", "antibiotico",
    "melatonina", "suplemento",
}

# Radicais de palavras que qualificam o nível de um resultado.
NIVEIS = {
    "alto": r"\balt[oa]s?\b|\baltissim[oa]s?\b",
    "elevado": r"\belevad[oa]s?\b",
    "baixo": r"\bbaix[oa]s?\b|\bbaixissim[oa]s?\b",
    "moderado": r"\bmoderad[oa]s?\b|\bmoderadamente\b",
    "leve": r"\bleves?\b|\blevemente\b",
    "aumentado": r"\baumentad[oa]s?\b",
    "reduzido": r"\breduzid[oa]s?\b",
    "lento": r"\blent[oa]s?\b|\blentamente\b",
    "rapido": r"\brapid[oa]s?\b|\brapidamente\b",
    "grave": r"\bgraves?\b",
    "severo": r"\bsever[oa]s?\b",
}

# Uma afirmação de diagnóstico não conta quando vem negada ou como hipótese na mesma frase:
# "não quer dizer que você terá a doença", "o teste não diz se você tem pressão alta".
NEGACAO_ANTES = re.compile(
    r"\bnao (quer dizer|significa|diz|indica|garante|afirma|confirma|determina|implica|mostra|aponta|"
    r"da para (dizer|saber|afirmar)|e possivel (dizer|saber|afirmar))( que| se)?[^.!?]{0,30}$"
)

# Padrões aplicados ao texto normalizado (minúsculas, sem acentos).
_DOENCAS = r"(doenca|diabetes|diabetic\w+|hipertens\w+|pressao alta|celiac\w+|intoleran\w+)"
PADROES_INSEGUROS = [
    ("diagnostico", re.compile(
        r"\bvoce (nao )?(tem|possui|esta com|sofre de|tera|vai ter|vai desenvolver|desenvolvera|e)\s+"
        r"(a |o |uma |um )?" + _DOENCAS
    )),
    ("diagnostico", re.compile(r"\b(foi|esta|sera) diagnosticad\w+|\b(seu|o) diagnostico e\b|\bdiagnostico (confirmado|positivo)\b")),
    ("prescricao", re.compile(
        r"\b(tome|tomar|use|utilize|inicie|comece a tomar|suspenda|pare de tomar|interrompa|aumente|reduza)\b"
        r".{0,40}\b(medicamento\w*|remedio\w*|comprimido\w*|capsula\w*|dose\w*|medicac\w+)\b"
    )),
    ("dose", re.compile(r"\b\d+([.,]\d+)?\s?(mg|mcg|ml|ui|gotas|comprimidos?)\b")),
]


def remover_citacoes(texto: str) -> str:
    return re.sub(r"\s*" + REGEX_CITACAO.pattern, "", texto)


_ID_FONTE = r"[a-z-]+:[a-z0-9-]+"
REGEX_CITACAO_MULTIPLA = re.compile(rf"\[({_ID_FONTE}(?:\s*[,;]\s*{_ID_FONTE})+)\]")


def normalizar_citacoes(texto: str) -> str:
    """
    O LLM às vezes cita duas fontes no mesmo colchete: "[fonte-a, fonte-b]".
    Separa em "[fonte-a][fonte-b]", o formato que a auditoria e a interface reconhecem.
    """
    return REGEX_CITACAO_MULTIPLA.sub(
        lambda m: "".join(f"[{fonte.strip()}]" for fonte in re.split(r"[,;]", m.group(1))), texto
    )


def contar_silabas(palavra: str) -> int:
    """Aproximação: cada grupo de vogais conta como uma sílaba."""
    return max(1, len(re.findall(r"[aeiouy]+", normalizar(palavra))))


def indice_flesch(texto: str) -> float:
    """
    Índice de legibilidade de Flesch adaptado ao português (Martins et al., 1996):
    248,835 - 1,015 * (palavras por frase) - 84,6 * (sílabas por palavra).
    Acima de 50 o texto é considerado fácil; abaixo de 25, muito difícil.
    """
    frases = dividir_frases(texto)
    palavras = re.findall(r"[A-Za-zÀ-ÿ]+", texto)
    if not frases or not palavras:
        return 0.0
    silabas = sum(contar_silabas(palavra) for palavra in palavras)
    return round(248.835 - 1.015 * (len(palavras) / len(frases)) - 84.6 * (silabas / len(palavras)), 1)


def _passagens_contexto(trechos: Sequence) -> Tuple[List[str], List[str]]:
    textos, origens = [], []
    for trecho in trechos:
        chunk = trecho.chunk
        linhas = chunk.texto.split("\n")
        candidatos = [chunk.texto] + chunk.passagens + linhas + [l.split(": ", 1)[-1] for l in linhas]
        for texto in dict.fromkeys(c for c in candidatos if c and c.strip()):
            textos.append(texto)
            origens.append(chunk.id)
    for frase in FRASES_PERMITIDAS:
        textos.append(frase)
        origens.append("frase-de-seguranca")
    return textos, origens


def avaliar_frases(resposta: str, trechos: Sequence) -> List[Dict[str, Any]]:
    """
    Para cada frase da resposta, encontra a passagem do contexto mais parecida.
    Devolve o apoio (similaridade de cosseno, 0 a 1) e de qual trecho ele veio.
    """
    frases = [f for f in dividir_frases(remover_citacoes(resposta)) if len(tokenizar(f)) >= 2]
    if not frases:
        return []

    passagens, origens = _passagens_contexto(trechos)
    vetores = np.array(gerar_embeddings(frases) + gerar_embeddings(passagens, usar_cache=True))
    vetores /= np.linalg.norm(vetores, axis=1, keepdims=True)
    similaridades = vetores[: len(frases)] @ vetores[len(frases):].T

    resultado = []
    for frase, linha in zip(frases, similaridades):
        melhor = int(linha.argmax())
        resultado.append({
            "frase": frase,
            "apoio": round(float(linha[melhor]), 3),
            "fonte": origens[melhor],
            "apoiada": bool(linha[melhor] >= LIMIAR_FRASE),
        })
    return resultado


def _checagem(nome: str, ok: bool, bloqueante: bool, valor: Any, detalhe: str) -> Dict[str, Any]:
    return {"nome": nome, "ok": bool(ok), "bloqueante": bloqueante, "valor": valor, "detalhe": detalhe}


def checar_seguranca(resposta: str, contexto: str) -> Dict[str, Any]:
    texto = normalizar(remover_citacoes(resposta))
    contexto_normalizado = normalizar(contexto)

    violacoes = []
    for tipo, padrao in PADROES_INSEGUROS:
        for ocorrencia in padrao.finditer(texto):
            negada = tipo == "diagnostico" and NEGACAO_ANTES.search(texto[max(0, ocorrencia.start() - 70):ocorrencia.start()])
            if not negada:
                violacoes.append(tipo)
                break
    medicamentos = sorted(
        m for m in MEDICAMENTOS
        if re.search(rf"\b{m}\w*\b", texto) and m not in contexto_normalizado
    )
    if medicamentos:
        violacoes.append("medicamento")

    violacoes = sorted(set(violacoes))
    detalhe = "sem linguagem de diagnóstico ou prescrição"
    if violacoes:
        detalhe = "encontrado: " + ", ".join(violacoes)
        if medicamentos:
            detalhe += f" ({', '.join(medicamentos)})"
    return _checagem("seguranca", not violacoes, True, violacoes, detalhe)


def checar_niveis(resposta: str, contexto: str) -> Dict[str, Any]:
    """
    Palavras que qualificam um resultado (alto, baixo, moderado, lento...) só podem aparecer
    na resposta se constarem no contexto. A similaridade de embeddings não distingue
    "baixa predisposição" de "alta predisposição"; esta checagem cobre essa inversão.
    """
    texto = normalizar(remover_citacoes(resposta))
    contexto_normalizado = normalizar(contexto)
    trocados = sorted(
        nivel for nivel, padrao in NIVEIS.items()
        if re.search(padrao, texto) and not re.search(padrao, contexto_normalizado)
    )
    return _checagem(
        "niveis", not trocados, True, trocados,
        "os níveis citados conferem com o relatório" if not trocados
        else "qualificadores que não constam no relatório: " + ", ".join(trocados),
    )


def aquecer(chunks: Sequence) -> int:
    """Pré-calcula os embeddings das passagens usadas na checagem de fundamentação."""
    passagens, _ = _passagens_contexto([SimpleNamespace(chunk=chunk) for chunk in chunks])
    gerar_embeddings(passagens, usar_cache=True)
    return len(passagens)


def validar_resposta(resposta: str, trechos: Sequence, nivel: str = "simples", pergunta: str = "",
                     resumo: bool = False) -> Dict[str, Any]:
    """
    Executa todas as checagens sobre uma resposta e devolve o parecer.
    A resposta é aprovada quando nenhuma checagem bloqueante falha.
    """
    contexto = "\n".join(trecho.chunk.texto for trecho in trechos)
    ids_recuperados = {trecho.chunk.id for trecho in trechos}
    texto_limpo = remover_citacoes(resposta)
    checagens = []

    # 1. fundamentação
    frases = avaliar_frases(resposta, trechos)
    apoiadas = sum(1 for frase in frases if frase["apoiada"])
    proporcao = round(apoiadas / len(frases), 2) if frases else 0.0
    sem_apoio = [frase["frase"] for frase in frases if not frase["apoiada"]]
    checagens.append(_checagem(
        "fundamentacao", bool(frases) and proporcao >= MINIMO_FRASES_APOIADAS, True, proporcao,
        f"{apoiadas} de {len(frases)} frases com apoio no relatório"
        + (f"; sem apoio: \"{sem_apoio[0]}\"" if sem_apoio else ""),
    ))

    # 2. números
    permitidos = set(extrair_numeros(contexto)) | set(extrair_numeros(pergunta))
    inventados = sorted(set(extrair_numeros(texto_limpo)) - permitidos)
    checagens.append(_checagem(
        "numeros", not inventados, True, inventados,
        "todos os números constam no relatório" if not inventados
        else "números que não constam no relatório: " + ", ".join(inventados),
    ))

    # 3. citações
    citadas = set(REGEX_CITACAO.findall(resposta))
    invalidas = sorted(citadas - ids_recuperados)
    if not citadas:
        detalhe = "a resposta não cita nenhuma fonte"
    elif invalidas:
        detalhe = "fontes citadas que não foram recuperadas: " + ", ".join(invalidas)
    else:
        detalhe = "fontes citadas: " + ", ".join(sorted(citadas))
    checagens.append(_checagem("citacoes", bool(citadas) and not invalidas, True, sorted(citadas), detalhe))

    # 4. segurança
    checagens.append(checar_seguranca(resposta, contexto))

    # 5. níveis de resultado
    checagens.append(checar_niveis(resposta, contexto))

    # 6. tamanho
    limite = MAX_PALAVRAS_RESUMO if resumo else MAX_PALAVRAS
    palavras = len(texto_limpo.split())
    checagens.append(_checagem("tamanho", 0 < palavras <= limite, True, palavras, f"{palavras} palavras (limite {limite})"))

    # 7. legibilidade (informativa)
    flesch = indice_flesch(texto_limpo)
    facil = nivel != "simples" or flesch >= FLESCH_MINIMO_SIMPLES
    checagens.append(_checagem(
        "legibilidade", facil, False, flesch,
        f"índice de Flesch {flesch}" + ("" if facil else f" (abaixo de {FLESCH_MINIMO_SIMPLES} para linguagem simples)"),
    ))

    return {
        "aprovada": all(c["ok"] for c in checagens if c["bloqueante"]),
        "checagens": checagens,
        "frases": frases,
    }


def motivos_reprovacao(validacao: Dict[str, Any]) -> List[str]:
    return [f"{c['nome']}: {c['detalhe']}" for c in validacao["checagens"] if c["bloqueante"] and not c["ok"]]
