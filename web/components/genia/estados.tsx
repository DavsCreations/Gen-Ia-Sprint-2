import { CircleAlertIcon } from "lucide-react";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/reui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function ErroDeCarga({ mensagem, aoTentar }: { mensagem: string; aoTentar: () => void }) {
  return (
    <Alert variant="destructive">
      <CircleAlertIcon aria-hidden />
      <AlertTitle>Não foi possível carregar</AlertTitle>
      <AlertDescription>{mensagem}</AlertDescription>
      <AlertAction>
        <Button variant="outline" size="sm" onClick={aoTentar}>
          Tentar de novo
        </Button>
      </AlertAction>
    </Alert>
  );
}

export function Esqueleto({ linhas = 3 }: { linhas?: number }) {
  return (
    <div className="grid gap-2" aria-busy="true" aria-label="Carregando">
      {Array.from({ length: linhas }, (_, indice) => (
        <Skeleton key={indice} className="h-4" style={{ width: `${100 - indice * 12}%` }} />
      ))}
    </div>
  );
}

export function Secao({
  titulo,
  descricao,
  acao,
  children,
}: {
  titulo: string;
  descricao?: string;
  acao?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="grid gap-3">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
        <div className="grid gap-0.5">
          <h2 className="text-base font-semibold tracking-tight">{titulo}</h2>
          {descricao && <p className="text-sm text-muted-foreground">{descricao}</p>}
        </div>
        {acao && <div className="ml-auto">{acao}</div>}
      </div>
      {children}
    </section>
  );
}

/** Indicador de um único número (não é gráfico: um valor não precisa de eixo). */
export function Indicador({ rotulo, valor, nota }: { rotulo: string; valor: string; nota?: string }) {
  return (
    <div className="grid gap-1 rounded-xl border bg-card p-4">
      <span className="text-xs text-muted-foreground">{rotulo}</span>
      <span className="text-2xl font-semibold tracking-tight">{valor}</span>
      {nota && <span className="text-xs text-muted-foreground">{nota}</span>}
    </div>
  );
}
