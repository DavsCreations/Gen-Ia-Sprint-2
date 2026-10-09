import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from app.config import CAMINHO_RELATORIO


NOMES_SECOES = {
    "ancestralidade": "Ancestralidade",
    "saude_genetica": "Saúde genética",
    "bem_estar": "Bem-estar",
    "disclaimers": "Avisos",
}

CAMPOS_RAIZ = {"id_relatorio", "tipo_relatorio", "paciente", *NOMES_SECOES}
CAMPOS_COMPOSICAO = {"origem", "percentual", "explicacao"}
CAMPOS_BEM_ESTAR = {"tema", "resultado", "explicacao_tecnica", "explicacao_simples", "recomendacao"}
CAMPOS_SAUDE = CAMPOS_BEM_ESTAR | {"nivel_risco"}


@dataclass
class Chunk:
    """
    Trecho do relatório indexado na base vetorial.
    O id é estável (derivado da seção e do tema) para permitir rastrear a fonte de cada resposta.
    """
    id: str
    secao: str
    tema: str
    texto: str
    campos: Dict[str, Any] = field(default_factory=dict)
    # Passagens curtas do chunk, indexadas individualmente: uma pergunta curta casa melhor
    # com uma frase do que com o chunk inteiro. A busca devolve sempre o chunk pai.
    passagens: List[str] = field(default_factory=list)


def carregar_relatorio(caminho: str | Path = CAMINHO_RELATORIO) -> Dict[str, Any]:
    with open(caminho, 'r', encoding='utf-8') as arquivo:
        dados = json.load(arquivo)
    return dados


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def _percentual(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",") + "%"


def _problema(nivel: str, caminho: str, mensagem: str) -> Dict[str, str]:
    return {"nivel": nivel, "caminho": caminho, "mensagem": mensagem}


def _validar_itens(itens: Any, caminho: str, campos: set) -> List[Dict[str, str]]:
    if not isinstance(itens, list) or not itens:
        return [_problema("erro", caminho, "deve ser uma lista com ao menos um item")]

    problemas = []
    for i, item in enumerate(itens):
        local = f"{caminho}[{i}]"
        if not isinstance(item, dict):
            problemas.append(_problema("erro", local, "item deve ser um objeto"))
            continue
        for campo in sorted(campos - item.keys()):
            problemas.append(_problema("erro", local, f"campo obrigatório ausente: {campo}"))
        for campo in sorted(item.keys() - campos):
            problemas.append(_problema("aviso", local, f"campo desconhecido (será ignorado): {campo}"))
        for campo in sorted(campos & item.keys()):
            if campo != "percentual" and not str(item[campo]).strip():
                problemas.append(_problema("erro", local, f"campo vazio: {campo}"))
    return problemas


def validar_relatorio(relatorio: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Verifica a estrutura do relatório antes da indexação.
    Retorna a lista de problemas encontrados ("erro" impede a ingestão; "aviso" apenas registra).
    Campos desconhecidos são sinalizados porque um nome de chave divergente faz o dado
    sumir da base sem gerar erro algum.
    """
    problemas: List[Dict[str, str]] = []

    for campo in sorted(set(NOMES_SECOES) | {"id_relatorio"}):
        if campo not in relatorio:
            problemas.append(_problema("erro", campo, "seção obrigatória ausente"))
    for campo in sorted(relatorio.keys() - CAMPOS_RAIZ):
        problemas.append(_problema("aviso", campo, "seção desconhecida (será ignorada)"))

    ancestral = relatorio.get("ancestralidade")
    if isinstance(ancestral, dict):
        if not str(ancestral.get("resumo", "")).strip():
            problemas.append(_problema("erro", "ancestralidade.resumo", "campo obrigatório ausente"))
        for campo in sorted(ancestral.keys() - {"resumo", "composicao"}):
            problemas.append(_problema("aviso", f"ancestralidade.{campo}", "campo desconhecido (será ignorado)"))

        composicao = ancestral.get("composicao")
        problemas += _validar_itens(composicao, "ancestralidade.composicao", CAMPOS_COMPOSICAO)
        if isinstance(composicao, list):
            percentuais = [i.get("percentual") for i in composicao if isinstance(i, dict)]
            if all(isinstance(p, (int, float)) and 0 <= p <= 100 for p in percentuais):
                if percentuais and abs(sum(percentuais) - 100) > 0.5:
                    problemas.append(_problema(
                        "aviso", "ancestralidade.composicao",
                        f"percentuais somam {sum(percentuais):.1f}, esperado 100",
                    ))
            else:
                problemas.append(_problema(
                    "erro", "ancestralidade.composicao", "percentual deve ser um número entre 0 e 100"
                ))

    if "saude_genetica" in relatorio:
        problemas += _validar_itens(relatorio["saude_genetica"], "saude_genetica", CAMPOS_SAUDE)
    if "bem_estar" in relatorio:
        problemas += _validar_itens(relatorio["bem_estar"], "bem_estar", CAMPOS_BEM_ESTAR)

    avisos = relatorio.get("disclaimers")
    if "disclaimers" in relatorio and (not isinstance(avisos, list) or not avisos):
        problemas.append(_problema("erro", "disclaimers", "deve ser uma lista com ao menos um aviso"))

    return problemas


def _chunk_tema(item: Dict[str, Any], chave_secao: str) -> Chunk:
    linhas = [f"Tema: {item.get('tema')}", f"Resultado: {item.get('resultado')}"]
    if item.get("nivel_risco"):
        linhas.append(f"Nível de risco: {item.get('nivel_risco')}")
    linhas += [
        f"Explicação técnica: {item.get('explicacao_tecnica')}",
        f"Explicação simples: {item.get('explicacao_simples')}",
        f"Recomendação: {item.get('recomendacao')}",
    ]
    prefixo = "saude" if chave_secao == "saude_genetica" else "bem-estar"
    tema = str(item.get("tema"))
    return Chunk(
        id=f"{prefixo}:{_slug(tema)}",
        secao=NOMES_SECOES[chave_secao],
        tema=tema,
        texto="\n".join(linhas),
        campos=dict(item),
        passagens=[
            f"{tema}: {item.get('resultado')}",
            f"{tema}. {item.get('explicacao_simples')}",
            f"{tema}. {item.get('explicacao_tecnica')}",
            f"{tema}. {item.get('recomendacao')}",
        ],
    )


def criar_chunks(relatorio: Dict[str, Any]) -> List[Chunk]:
    """
    Divide o relatório em chunks por tema.
    Os dados de identificação do paciente não são indexados (minimização de dados).
    """
    chunks: List[Chunk] = []

    # ancestralidade
    if "ancestralidade" in relatorio:
        ancestral = relatorio["ancestralidade"]
        composicao = ancestral.get("composicao", [])

        linhas = ["Tema: Ancestralidade (visão geral)"]
        if "resumo" in ancestral:
            linhas.append(f"Resumo: {ancestral['resumo']}")
        if composicao:
            partes = [f"{i.get('origem')} {_percentual(i.get('percentual', 0))}" for i in composicao]
            linhas.append("Composição: " + "; ".join(partes))
        chunks.append(Chunk(
            id="ancestralidade:visao-geral",
            secao=NOMES_SECOES["ancestralidade"],
            tema="Ancestralidade",
            texto="\n".join(linhas),
            campos={"resumo": ancestral.get("resumo"), "composicao": composicao},
            passagens=linhas[1:],
        ))

        for item in composicao:
            texto = (
                f"Tema: Ancestralidade {item.get('origem')}\n"
                f"Percentual: {_percentual(item.get('percentual', 0))}\n"
                f"Explicação: {item.get('explicacao')}"
            )
            chunks.append(Chunk(
                id=f"ancestralidade:{_slug(str(item.get('origem')))}",
                secao=NOMES_SECOES["ancestralidade"],
                tema=f"Ancestralidade {item.get('origem')}",
                texto=texto,
                campos=dict(item),
            ))

    # saúde genética
    for item in relatorio.get("saude_genetica", []):
        chunks.append(_chunk_tema(item, "saude_genetica"))

    # bem-estar
    for item in relatorio.get("bem_estar", []):
        chunks.append(_chunk_tema(item, "bem_estar"))

    # disclaimers: um único chunk, para não competir com os temas na busca
    avisos = relatorio.get("disclaimers", [])
    if avisos:
        chunks.append(Chunk(
            id="avisos:limites-do-relatorio",
            secao=NOMES_SECOES["disclaimers"],
            tema="Avisos e limites do relatório",
            texto="Tema: Avisos e limites do relatório\n" + "\n".join(f"- {a}" for a in avisos),
            campos={"avisos": list(avisos)},
            passagens=list(avisos),
        ))

    return chunks


if __name__ == "__main__":
    relatorio = carregar_relatorio()

    for problema in validar_relatorio(relatorio):
        print(f"[{problema['nivel'].upper()}] {problema['caminho']}: {problema['mensagem']}")

    chunks = criar_chunks(relatorio)

    print("\n===== CHUNKS GERADOS =====\n")
    for chunk in chunks:
        print(f"CHUNK {chunk.id}")
        print(chunk.texto)
        print("\n----------------------\n")
