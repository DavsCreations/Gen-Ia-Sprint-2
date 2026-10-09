"""
Camada de acesso ao LLM.

Qualquer provedor com API compatível com a da OpenAI (chat/completions) funciona.
Há três predefinições: Groq e Gemini (nuvem, com plano gratuito) e Ollama (modelo local,
em que nenhum dado sai da máquina). Sem provedor configurado, o sistema opera em modo
"extrativo": responde apenas com frases do próprio relatório, sem geração.
"""
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx

from app import config  # noqa: F401 — importar a configuração garante a leitura do .env

PROVEDORES = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "variavel_chave": "GROQ_API_KEY",
        "modelo": "llama-3.3-70b-versatile",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "variavel_chave": "GEMINI_API_KEY",
        "modelo": "gemini-3.8-flash",
        # O modelo "pensa" antes de responder e esse raciocínio consome o limite de tokens: sem
        # desligar, a resposta vinha cortada. A tarefa (reescrever trechos dados) dispensa raciocínio,
        # e sem ele a resposta sai mais rápida e mais estável.
        "raciocinio": "none",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "variavel_chave": None,
        "modelo": "llama3.2",
    },
}

MODO_EXTRATIVO = "extrativo"


class ErroLLM(Exception):
    """Falha ao obter resposta do provedor (rede, limite de uso, resposta inválida)."""


@dataclass(frozen=True)
class ConfigLLM:
    provedor: str
    modelo: str
    base_url: str = ""
    api_key: str = ""
    temperatura: float = 0.0
    timeout: float = 30.0
    raciocinio: str = ""

    @property
    def ativo(self) -> bool:
        return self.provedor != MODO_EXTRATIVO


def config_atual() -> ConfigLLM:
    """
    Lê a configuração do LLM das variáveis de ambiente.

    LLM_PROVIDER escolhe o provedor (groq, gemini, ollama ou extrativo). Se não for informado,
    usa o primeiro provedor de nuvem cuja chave esteja definida. LLM_BASE_URL, LLM_API_KEY e
    LLM_MODEL sobrescrevem a predefinição e permitem usar outro provedor compatível.
    """
    provedor = os.getenv("LLM_PROVIDER", "").strip().lower()

    if not provedor:
        if os.getenv("LLM_BASE_URL"):
            provedor = "personalizado"
        else:
            provedor = next(
                (nome for nome, p in PROVEDORES.items()
                 if p["variavel_chave"] and os.getenv(p["variavel_chave"])),
                MODO_EXTRATIVO,
            )

    if provedor == MODO_EXTRATIVO:
        return ConfigLLM(provedor=MODO_EXTRATIVO, modelo="sem-llm")

    predefinicao = PROVEDORES.get(provedor, {})
    variavel_chave = predefinicao.get("variavel_chave")

    return ConfigLLM(
        provedor=provedor,
        modelo=os.getenv("LLM_MODEL") or predefinicao.get("modelo", ""),
        base_url=(os.getenv("LLM_BASE_URL") or predefinicao.get("base_url", "")).rstrip("/"),
        api_key=os.getenv("LLM_API_KEY") or (os.getenv(variavel_chave, "") if variavel_chave else ""),
        # Temperatura 0 por padrão: privilegia consistência entre respostas à mesma pergunta.
        temperatura=float(os.getenv("LLM_TEMPERATURE", "0")),
        timeout=float(os.getenv("LLM_TIMEOUT", "30")),
        raciocinio=os.getenv("LLM_REASONING_EFFORT", predefinicao.get("raciocinio", "")),
    )


def gerar(mensagens: List[Dict[str, str]], config: Optional[ConfigLLM] = None,
          temperatura: Optional[float] = None, max_tokens: int = 2000) -> str:
    """
    Envia as mensagens ao LLM e devolve o texto gerado.
    Tenta novamente uma vez em caso de limite de uso (429) ou erro do servidor (5xx).
    """
    config = config or config_atual()
    if not config.ativo:
        raise ErroLLM("nenhum provedor de LLM configurado")
    if not config.base_url or not config.modelo:
        raise ErroLLM(f"provedor '{config.provedor}' sem base_url ou modelo definidos")

    cabecalhos = {"Content-Type": "application/json"}
    if config.api_key:
        cabecalhos["Authorization"] = f"Bearer {config.api_key}"

    corpo = {
        "model": config.modelo,
        "messages": mensagens,
        "temperature": config.temperatura if temperatura is None else temperatura,
        "max_tokens": max_tokens,
    }
    if config.raciocinio:
        corpo["reasoning_effort"] = config.raciocinio

    ultimo_erro = ""
    for tentativa in range(2):
        try:
            resposta = httpx.post(
                f"{config.base_url}/chat/completions",
                headers=cabecalhos, json=corpo, timeout=config.timeout,
            )
        except httpx.HTTPError as erro:
            ultimo_erro = f"falha de rede: {type(erro).__name__}"
        else:
            if resposta.status_code == 200:
                try:
                    escolha = resposta.json()["choices"][0]
                    texto = escolha["message"].get("content")
                except (KeyError, IndexError, TypeError, ValueError, AttributeError):
                    raise ErroLLM("resposta do provedor em formato inesperado")
                if escolha.get("finish_reason") == "length":
                    # Uma resposta cortada no meio não deve ser exibida nem auditada.
                    raise ErroLLM("resposta cortada pelo limite de tokens")
                if not texto or not texto.strip():
                    raise ErroLLM("o provedor devolveu uma resposta vazia")
                return texto.strip()

            ultimo_erro = f"HTTP {resposta.status_code}"
            if resposta.status_code != 429 and resposta.status_code < 500:
                break

        if tentativa == 0:
            time.sleep(1.5)

    raise ErroLLM(f"provedor '{config.provedor}' indisponível ({ultimo_erro})")
