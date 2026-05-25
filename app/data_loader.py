import json
from typing import Any, Dict, List


def carregar_relatorio(caminho: str) -> Dict[str, Any]:
    with open(caminho, 'r', encoding='utf-8') as arquivo:
        dados = json.load(arquivo)
    return dados


def criar_chunks(relatorio: Dict[str, Any]) -> List[str]:
    chunks: List[str] = []

    # ancestralidade
    if "ancestralidade" in relatorio:
        ancestral = relatorio["ancestralidade"]
        if "resumo" in ancestral:
            chunks.append(ancestral["resumo"])

        for item in ancestral.get("composição", []):
            texto = (
                f"origem: {item.get('origem')}\n"
                f"percentual: {item.get('percentual')}%\n"
                f"explicação: {item.get('explicação')}\n"
            )
            chunks.append(texto)

    # saúde genética
    for item in relatorio.get("saude_genetica", []):
        texto = (
            f"Tema: {item.get('tema')}\n"
            f"Resultado: {item.get('resultado')}\n"
            f"Explicação técnica: {item.get('explicacao_tecnica')}\n"
            f"Explicação simples: {item.get('explicacao_simples')}\n"
            f"Recomendação: {item.get('recomendacao')}\n"
        )
        chunks.append(texto)

    # bem-estar
    for item in relatorio.get("bem_estar", []):
        texto = (
            f"Tema: {item.get('tema')}\n"
            f"Resultado: {item.get('resultado')}\n"
            f"Explicação técnica: {item.get('explicacao_tecnica')}\n"
            f"Explicação simples: {item.get('explicacao_simples')}\n"
            f"Recomendação: {item.get('recomendacao')}\n"
        )
        chunks.append(texto)

    # disclaimers
    for aviso in relatorio.get("disclaimers", []):
        chunks.append(aviso)

    return chunks


if __name__ == "__main__":
    relatorio = carregar_relatorio("data/relatorio_exemplo.json")
    chunks = criar_chunks(relatorio)

    print("\n===== CHUNKS GERADOS =====\n")
    for i, chunk in enumerate(chunks):
        print(f"CHUNK {i+1}")
        print(chunk)
        print("\n----------------------\n")
        