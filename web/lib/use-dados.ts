"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";

type Estado<T> = { caminho: string | null; chave: string | null; dados: T | null; erro: string | null };

/**
 * Busca um recurso da API quando `habilitado` e expõe `recarregar` para atualizar sob demanda.
 * Ao recarregar o mesmo caminho, os dados anteriores continuam visíveis até os novos chegarem.
 */
export function useDados<T>(caminho: string, habilitado = true) {
  const [estado, setEstado] = useState<Estado<T>>({ caminho: null, chave: null, dados: null, erro: null });
  const [versao, setVersao] = useState(0);
  const chave = `${caminho}#${versao}`;

  useEffect(() => {
    if (!habilitado) return;
    let ativo = true;
    api<T>(caminho)
      .then((dados) => ativo && setEstado({ caminho, chave, dados, erro: null }))
      .catch(
        (falha: Error) =>
          ativo &&
          setEstado((anterior) => ({
            caminho,
            chave,
            dados: anterior.caminho === caminho ? anterior.dados : null,
            erro: falha.message,
          })),
      );
    return () => {
      ativo = false;
    };
  }, [caminho, chave, habilitado]);

  const recarregar = useCallback(() => setVersao((v) => v + 1), []);

  return {
    dados: estado.caminho === caminho ? estado.dados : null,
    erro: estado.chave === chave ? estado.erro : null,
    carregando: habilitado && estado.chave !== chave,
    recarregar,
  };
}
