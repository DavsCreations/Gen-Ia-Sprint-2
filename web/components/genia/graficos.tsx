"use client";

import { useState } from "react";

import type { ItemComposicao } from "@/lib/api";
import { cn } from "@/lib/utils";

const CORES = ["var(--viz-1)", "var(--viz-2)", "var(--viz-3)", "var(--viz-4)"];

function percentual(valor: number): string {
  return `${valor.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

/**
 * Composição de ancestralidade: barra empilhada (parte de um todo) com legenda que
 * também funciona como tabela — todo valor está escrito, nunca só na cor.
 */
export function GraficoAncestralidade({ composicao }: { composicao: ItemComposicao[] }) {
  const [ativa, setAtiva] = useState<string | null>(null);
  const destaque = composicao.find((item) => item.origem === ativa);

  return (
    <figure className="grid gap-4">
      <div
        className="flex h-6 w-full gap-0.5"
        role="img"
        aria-label={"Composição de ancestralidade: " + composicao.map((i) => `${i.origem} ${percentual(i.percentual)}`).join(", ")}
      >
        {composicao.map((item, indice) => (
          <button
            key={item.origem}
            type="button"
            aria-label={`${item.origem}: ${percentual(item.percentual)}`}
            onMouseEnter={() => setAtiva(item.origem)}
            onMouseLeave={() => setAtiva(null)}
            onFocus={() => setAtiva(item.origem)}
            onBlur={() => setAtiva(null)}
            className={cn(
              "h-full min-w-1.5 rounded-[4px] outline-offset-2 transition-opacity focus-visible:outline-2 focus-visible:outline-ring",
              ativa && ativa !== item.origem && "opacity-40",
            )}
            style={{ width: `${item.percentual}%`, background: CORES[indice % CORES.length] }}
          />
        ))}
      </div>

      <figcaption className="grid gap-1.5 sm:grid-cols-2">
        {composicao.map((item, indice) => (
          <div
            key={item.origem}
            onMouseEnter={() => setAtiva(item.origem)}
            onMouseLeave={() => setAtiva(null)}
            className={cn(
              "flex items-baseline gap-2 rounded-md px-2 py-1 text-sm transition-colors",
              ativa === item.origem && "bg-muted",
            )}
          >
            <span
              className="size-2.5 shrink-0 translate-y-px rounded-[3px]"
              style={{ background: CORES[indice % CORES.length] }}
              aria-hidden
            />
            <span>{item.origem}</span>
            <span className="ml-auto font-medium tabular-nums">{percentual(item.percentual)}</span>
          </div>
        ))}
      </figcaption>

      <p className="min-h-10 text-sm text-muted-foreground" aria-live="polite">
        {destaque ? destaque.explicacao : "Passe o cursor ou toque em uma origem para ver o que ela indica."}
      </p>
    </figure>
  );
}

const NIVEIS = ["Baixo", "Baixo a moderado", "Moderado", "Alto"];

/**
 * Nível de risco em escala ordinal de quatro posições. Usa um único matiz (do claro ao
 * escuro) em vez de verde/vermelho: predisposição não é alarme, e o rótulo vem sempre escrito.
 */
export function MedidorDeRisco({ nivel }: { nivel: string }) {
  const posicao = NIVEIS.findIndex((n) => n.toLowerCase() === nivel.trim().toLowerCase());
  if (posicao < 0) return <span className="text-sm text-muted-foreground">Nível de risco: {nivel}</span>;

  return (
    <div className="grid gap-1.5">
      <div className="flex gap-0.5" role="img" aria-label={`Nível de risco: ${nivel} (posição ${posicao + 1} de ${NIVEIS.length})`}>
        {NIVEIS.map((rotulo, indice) => (
          <span
            key={rotulo}
            className="h-1.5 flex-1 rounded-full"
            style={{ background: indice <= posicao ? `var(--viz-nivel-${posicao + 1})` : "var(--viz-trilho)" }}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Nível de risco: <span className="font-medium text-foreground">{nivel}</span>
        <span className="sr-only"> (escala de baixo a alto)</span>
      </p>
    </div>
  );
}

/** Barras horizontais de uma única série (contagens por categoria), com o valor na ponta. */
export function BarrasHorizontais({ dados }: { dados: { rotulo: string; valor: number }[] }) {
  const maximo = Math.max(1, ...dados.map((d) => d.valor));
  if (dados.length === 0) return <p className="text-sm text-muted-foreground">Sem dados ainda.</p>;

  return (
    <div className="grid gap-2">
      {dados.map((dado) => (
        <div key={dado.rotulo} className="grid grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate text-muted-foreground" title={dado.rotulo}>
            {dado.rotulo}
          </span>
          <span className="h-3">
            <span
              className="block h-full min-w-0.5 rounded-r-[4px]"
              style={{ width: `${(dado.valor / maximo) * 100}%`, background: "var(--viz-1)" }}
              title={`${dado.rotulo}: ${dado.valor}`}
            />
          </span>
          <span className="w-8 text-right font-medium tabular-nums">{dado.valor}</span>
        </div>
      ))}
    </div>
  );
}
