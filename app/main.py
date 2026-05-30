from rag import gerar_resposta_formatada


def iniciar_chat():
    print("\n=== GENIA - ASSISTENTE GENÉTICO ===")
    print("Digite sua pergunta sobre o relatório genético.")
    print("Digite 'sair' para encerrar.\n")

    while True:
        pergunta = input("Você: ")

        if pergunta.lower() == "sair":
            print("Chat encerrado.")
            break

        resposta = gerar_resposta_formatada(pergunta)

        print("\nGenIA:")
        print(resposta)
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    iniciar_chat()