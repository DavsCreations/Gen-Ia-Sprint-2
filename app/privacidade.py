"""
Controles de privacidade aplicados em tempo de execução (LGPD).

- Mascaramento de dados pessoais digitados na pergunta, antes de o texto ser enviado
  ao LLM ou gravado no log.
- Pseudonimização do identificador de sessão: o log nunca guarda o identificador original.
"""
import hashlib
import os
import re
from typing import List, Tuple

VERSAO_TERMO = "2026-10"

# A ordem importa: CPF antes de telefone, pois ambos são sequências de 11 dígitos.
PADROES_PII = [
    ("cpf", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("telefone", re.compile(r"(?:\+?55\s?)?\(?\b\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b")),
    ("data", re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")),
]


def mascarar_pii(texto: str) -> Tuple[str, List[str]]:
    """
    Substitui dados pessoais reconhecíveis por marcadores (ex.: [CPF]).
    Devolve o texto mascarado e os tipos de dado encontrados.

    Limitação conhecida: nomes próprios não são detectados por expressão regular.
    """
    encontrados = []
    for tipo, padrao in PADROES_PII:
        texto, quantidade = padrao.subn(f"[{tipo.upper()}]", texto)
        if quantidade:
            encontrados.append(tipo)
    return texto, encontrados


def pseudonimizar(identificador: str) -> str:
    """Hash com sal do identificador de sessão. Não é reversível sem o sal."""
    sal = os.getenv("GENIA_SAL", "genia-desenvolvimento")
    return hashlib.sha256(f"{sal}:{identificador}".encode("utf-8")).hexdigest()[:16]
