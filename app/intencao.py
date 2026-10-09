"""
Classificação da intenção da pergunta, antes de qualquer busca ou geração.

Duas camadas:
1. Regras determinísticas para o que é questão de segurança — tentativa de injeção de
   instruções e pedido de conselho médico (medicamento, dose, tratamento, sintomas).
   Segurança não depende de um modelo estatístico treinado com poucos exemplos, e uma
   regra pode ser lida e auditada.
2. Classificador scikit-learn (regressão logística sobre os embeddings da pergunta),
   treinado com data/intencoes.json, para as demais intenções.

Na avaliação da Sprint 4 o classificador original (TF-IDF de caracteres) foi trocado pelo
de embeddings, e as regras de conselho médico foram acrescentadas depois que dois pedidos
passaram pela triagem — ver docs/avaliacao.md.
"""
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression

from app.config import RAIZ
from app.rag import gerar_embeddings
from app.texto import normalizar

CAMINHO_INTENCOES = RAIZ / "data" / "intencoes.json"

INTENCAO_RELATORIO = "relatorio"
INTENCAO_CONSELHO = "conselho_medico"
INTENCAO_FORA = "fora_escopo"
INTENCAO_SAUDACAO = "saudacao"
INTENCAO_INJECAO = "injecao"

# Padrões aplicados ao texto normalizado (minúsculas, sem acentos).
PADROES_INJECAO = [
    r"\b(ignor\w+|desconsider\w+|esquec\w+|descart\w+)\b.{0,40}\b(instruc\w+|regra\w*|orientac\w+|prompt|anterior\w*|tudo)\b",
    r"\b(revel\w+|mostr\w+|repit\w+|exib\w+|imprim\w+|diga|escrev\w+)\b.{0,40}\b(prompt|instruc\w+ (do sistema|iniciais|internas)|suas (instruc\w+|regras))\b",
    r"\bprompt (do|de) sistema\b|\bsystem prompt\b",
    r"\b(aja|atue|comporte-se|finja|fingir|simule|responda)\b.{0,20}\b(como|ser|que)\b.{0,30}\b(medic\w+|doutor\w*|endocrinologista|especialista|outr\w+ (ia|assistente))\b",
    r"\b(voce agora e|a partir de agora voce|de agora em diante voce)\b",
    r"\bmodo (desenvolvedor|dan|irrestrito|sem (filtro|restric\w+))\b|\bjailbreak\b",
    r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|above|all|instructions|rules)\b",
    r"\bsem (nenhuma? )?(restric\w+|regra\w*|filtro\w*|aviso\w*)\b",
]

PADROES_CONSELHO = [
    # medicamentos, doses e tratamentos
    r"\b(remedio\w*|medicamento\w*|medicac\w+|comprimido\w*|capsula\w*|dose\w*|dosagem|miligrama\w*|\d+\s?mg"
    r"|prescrev\w+|prescric\w+|tratamento\w*|cirurgia\w*|antibiotico\w*|suplemento\w*|anti-?hipertensivo\w*)\b",
    r"\b(me )?receit(e|ar)\b|\breceita medica\b",
    r"\b(metformina|losartana|captopril|enalapril|atenolol|omeprazol|sinvastatina|ozempic|semaglutida|melatonina)\b",
    r"\b(tomar|tomo|aplicar|aplico|parar|suspender|interromper|trocar|comecar|iniciar|aumentar|diminuir)\b.{0,30}\binsulina\b",
    # interpretação de sintomas e pedido de diagnóstico
    r"\b(estou com|ando|sinto|estou sentindo|venho sentindo|tenho sentido)\b.{0,50}\b(dor\w*|febre|tontura\w*|sede"
    r"|urinando|emagrecendo|cansac\w+|mancha\w*|sintoma\w*|enjoo\w*|nausea\w*|vomit\w+|sangramento\w*"
    r"|formigamento\w*|falta de ar|inchac\w+)\b",
    r"\b(isso e|e|sera que e) grave\b|\bo que (eu )?(tenho|pode ser)\s*\?*$|\b(me de|quero|preciso de) um diagnostico\b|\bestou doente\b",
    r"\b(que|qual|quais) exames?\b.{0,30}\b(devo|preciso|tenho que)\b",
]

_REGEX_INJECAO = [re.compile(padrao) for padrao in PADROES_INJECAO]
_REGEX_CONSELHO = [re.compile(padrao) for padrao in PADROES_CONSELHO]


@dataclass
class Intencao:
    rotulo: str
    confianca: float
    probabilidades: Dict[str, float]
    origem: str  # "regra" ou "classificador"


def carregar_exemplos() -> Tuple[List[str], List[str]]:
    with open(CAMINHO_INTENCOES, "r", encoding="utf-8") as arquivo:
        exemplos = json.load(arquivo)["exemplos"]
    textos, rotulos = [], []
    for rotulo, frases in exemplos.items():
        textos += frases
        rotulos += [rotulo] * len(frases)
    return textos, rotulos


def vetorizar(textos: Sequence[str], usar_cache: bool = False) -> np.ndarray:
    return np.array(gerar_embeddings(list(textos), usar_cache=usar_cache))


def criar_classificador() -> LogisticRegression:
    return LogisticRegression(C=10, class_weight="balanced", max_iter=2000)


@lru_cache(maxsize=1)
def obter_classificador() -> LogisticRegression:
    textos, rotulos = carregar_exemplos()
    # Os exemplos de treino são dados do projeto, não de usuários: podem ficar em cache.
    return criar_classificador().fit(vetorizar(textos, usar_cache=True), rotulos)


def detectar_injecao(pergunta: str) -> bool:
    texto = normalizar(pergunta)
    return any(regex.search(texto) for regex in _REGEX_INJECAO)


def detectar_conselho_medico(pergunta: str) -> bool:
    texto = normalizar(pergunta)
    return any(regex.search(texto) for regex in _REGEX_CONSELHO)


def classificar(pergunta: str, vetor: Optional[np.ndarray] = None) -> Intencao:
    if detectar_injecao(pergunta):
        return Intencao(INTENCAO_INJECAO, 1.0, {INTENCAO_INJECAO: 1.0}, "regra")
    if detectar_conselho_medico(pergunta):
        return Intencao(INTENCAO_CONSELHO, 1.0, {INTENCAO_CONSELHO: 1.0}, "regra")

    modelo = obter_classificador()
    vetor = vetorizar([pergunta]) if vetor is None else vetor.reshape(1, -1)
    probabilidades = dict(zip(modelo.classes_, modelo.predict_proba(vetor)[0].round(4).tolist()))
    rotulo = max(probabilidades, key=probabilidades.get)
    return Intencao(rotulo, probabilidades[rotulo], probabilidades, "classificador")
