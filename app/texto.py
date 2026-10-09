"""
Utilitários de texto em português usados pela busca lexical, pelo classificador de
intenção e pelo validador de respostas.
"""
import re
import unicodedata
from typing import List

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos", "em", "no", "na",
    "nos", "nas", "por", "para", "pra", "pro", "com", "sem", "sobre", "entre", "ate", "ao", "aos", "e",
    "ou", "mas", "que", "se", "como", "quando", "onde", "porque", "qual", "quais", "quanto", "quanta",
    "quantos", "quem", "eu", "me", "mim", "meu", "minha", "meus", "minhas", "voce", "seu", "sua", "ele",
    "ela", "isso", "isto", "esse", "essa", "este", "esta", "aquele", "aquela", "ser", "sou", "era",
    "foi", "sao", "estar", "esta", "estou", "ter", "tenho", "tem", "tinha", "ha", "haver", "posso",
    "pode", "devo", "deve", "vou", "vai", "faz", "fazer", "muito", "muita", "mais", "menos", "ja", "nao",
    "sim", "tambem", "so", "algum", "alguma", "algo", "tipo", "pessoa", "relatorio", "indica",
    "la", "ai", "the", "of",
    # Vocabulário genérico do domínio: aparece em quase todo tema e não ajuda a distingui-los.
    "risco", "predisposicao", "genetica", "genetico", "geneticas", "geneticos", "chance",
    "probabilidade", "tema", "resultado", "explicacao", "recomendacao", "tecnica", "simples",
}


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, para comparar textos sem depender de grafia."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower()


def _radical(palavra: str) -> str:
    """Stemming leve: remove o plural simples, o suficiente para casar treino/treinos."""
    if len(palavra) > 4 and palavra.endswith("es") and palavra[-3] in "rzl":
        return palavra[:-2]
    if len(palavra) > 3 and palavra.endswith("s"):
        return palavra[:-1]
    return palavra


def tokenizar(texto: str) -> List[str]:
    """Palavras relevantes do texto: normalizadas, sem stopwords e com stemming leve."""
    palavras = re.findall(r"[a-z]+", normalizar(texto))
    return [_radical(p) for p in palavras if p not in STOPWORDS and len(p) > 1]


def extrair_numeros(texto: str) -> List[str]:
    """Números do texto em formato canônico (vírgula decimal vira ponto; 62,50 == 62.5)."""
    numeros = []
    for bruto in re.findall(r"\d+(?:[.,]\d+)?", texto):
        valor = float(bruto.replace(",", "."))
        numeros.append(f"{valor:g}")
    return numeros


def dividir_frases(texto: str) -> List[str]:
    frases = re.split(r"(?<=[.!?])\s+|\n+", texto.strip())
    return [f.strip() for f in frases if f.strip()]
