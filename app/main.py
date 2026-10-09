from app.agentes import responder


def iniciar_chat():
    print("\n=== GENIA - ASSISTENTE GENÉTICO ===")
    print("Digite sua pergunta sobre o relatório genético.")
    print("Digite 'sair' para encerrar.\n")

    while True:
        pergunta = input("Você: ")

        if pergunta.lower() == "sair":
            print("Chat encerrado.")
            break

        if not pergunta.strip():
            continue

        resultado = responder(pergunta, sessao="terminal")

        print("\nGenIA:")
        print(resultado["resposta"])
        print(f"\n{resultado['aviso']}")
        print(f"\nComo cheguei a esta resposta: {resultado['explicacao']}")
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    iniciar_chat()
