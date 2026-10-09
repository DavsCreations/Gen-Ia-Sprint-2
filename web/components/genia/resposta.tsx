"use client";

import { useState } from "react";
import {
  CheckIcon,
  ChevronDownIcon,
  CircleAlertIcon,
  InfoIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
  XIcon,
} from "lucide-react";

import {
  api,
  ROTULOS_CHECAGEM,
  ROTULOS_STATUS,
  type Etapa,
  type Fonte,
  type Modelo,
  type Resposta,
  type Validacao,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { CopyButton } from "@/components/copy-button";
import { Badge } from "@/components/reui/badge";
import {
  Timeline,
  TimelineContent,
  TimelineDate,
  TimelineHeader,
  TimelineIndicator,
  TimelineItem,
  TimelineSeparator,
  TimelineTitle,
} from "@/components/reui/timeline";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const REGEX_CITACAO = /\[([a-z-]+:[a-z0-9-]+)\]/g;

/** Texto da resposta com cada citação [id] trocada por uma marca numerada que aponta para a fonte. */
export function TextoComFontes({ texto, fontes }: { texto: string; fontes: { id: string; tema: string }[] }) {
  const ordem: string[] = [];
  const partes = texto.split(REGEX_CITACAO);

  return (
    <p className="leading-relaxed whitespace-pre-line">
      {partes.map((parte, indice) => {
        if (indice % 2 === 0) {
          // A marca da fonte encosta na palavra anterior: tira o espaço que o modelo deixa antes do colchete.
          const texto = parte.replace(/\s+([.,;])/g, "$1");
          return <span key={indice}>{indice < partes.length - 1 ? texto.trimEnd() : texto}</span>;
        }
        if (!ordem.includes(parte)) ordem.push(parte);
        const fonte = fontes.find((f) => f.id === parte);
        return (
          <Tooltip key={indice}>
            <TooltipTrigger
              render={
                <sup className="ml-0.5 cursor-help rounded bg-muted px-1 py-px text-[0.65rem] font-medium text-muted-foreground" />
              }
            >
              {ordem.indexOf(parte) + 1}
            </TooltipTrigger>
            <TooltipContent>Fonte: {fonte ? fonte.tema : parte}</TooltipContent>
          </Tooltip>
        );
      })}
    </p>
  );
}

export function SeloValidacao({ validacao, modelo }: { validacao: Validacao; modelo: Modelo }) {
  if (modelo.modo === "mensagem_fixa") return <Badge variant="outline">Mensagem padrão</Badge>;
  return validacao.aprovada ? (
    <Badge variant="success-light">
      <CheckIcon aria-hidden /> Verificada pelo Auditor
    </Badge>
  ) : (
    <Badge variant="destructive-light">
      <CircleAlertIcon aria-hidden /> Reprovada pelo Auditor
    </Badge>
  );
}

function valorDaChecagem(nome: string, valor: unknown): string {
  if (nome === "fundamentacao" && typeof valor === "number") return `${Math.round(valor * 100)}% das frases`;
  if (nome === "tamanho" && typeof valor === "number") return `${valor} palavras`;
  if (nome === "legibilidade" && typeof valor === "number") {
    const faixa = valor >= 75 ? "muito fácil" : valor >= 50 ? "fácil" : valor >= 25 ? "difícil" : "muito difícil";
    return `Flesch ${valor.toLocaleString("pt-BR")} (${faixa})`;
  }
  return "";
}

export function ListaChecagens({ validacao }: { validacao: Validacao }) {
  if (validacao.checagens.length === 0) {
    return <p className="text-sm text-muted-foreground">Mensagem fixa: não passa por checagens de conteúdo.</p>;
  }
  return (
    <ul className="grid gap-1.5">
      {validacao.checagens.map((checagem) => (
        <li key={checagem.nome} className="flex items-start gap-2 text-sm">
          {checagem.ok ? (
            <CheckIcon className="mt-0.5 size-4 shrink-0 text-success" aria-label="Passou" />
          ) : checagem.bloqueante ? (
            <XIcon className="mt-0.5 size-4 shrink-0 text-destructive" aria-label="Falhou" />
          ) : (
            <InfoIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-label="Informativo" />
          )}
          <span>
            <span className="font-medium">{ROTULOS_CHECAGEM[checagem.nome] ?? checagem.nome}</span>
            {!checagem.bloqueante && <span className="text-muted-foreground"> (informativa)</span>}
            <span className="block text-muted-foreground">
              {valorDaChecagem(checagem.nome, checagem.valor) || checagem.detalhe}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}

function ListaFontes({ fontes }: { fontes: Fonte[] }) {
  if (fontes.length === 0) return <p className="text-sm text-muted-foreground">Nenhum trecho foi consultado.</p>;
  return (
    <ul className="grid gap-2">
      {fontes.map((fonte) => (
        <li key={fonte.id} className={cn("rounded-lg border p-3 text-sm", !fonte.usada_no_contexto && "opacity-60")}>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-medium">{fonte.tema}</span>
            <span className="text-xs text-muted-foreground">{fonte.secao}</span>
            <Badge variant={fonte.usada_no_contexto ? "primary-light" : "outline"} size="sm" className="ml-auto">
              {fonte.usada_no_contexto ? "usada na resposta" : "descartada"}
            </Badge>
          </div>
          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
            <span className="h-1.5 flex-1 rounded-full" style={{ background: "var(--viz-trilho)" }}>
              <span
                className="block h-full rounded-full"
                style={{ width: `${Math.max(0, Math.min(1, fonte.score)) * 100}%`, background: "var(--viz-1)" }}
              />
            </span>
            <span className="tabular-nums">
              relevância {fonte.score.toFixed(2)} (semântica {fonte.score_semantico.toFixed(2)} · lexical{" "}
              {fonte.score_lexical.toFixed(2)})
            </span>
          </div>
          <details className="mt-2">
            <summary className="cursor-pointer text-xs text-muted-foreground">Ver trecho do relatório</summary>
            <p className="mt-1.5 text-xs whitespace-pre-line text-muted-foreground">{fonte.texto}</p>
          </details>
        </li>
      ))}
    </ul>
  );
}

export function LinhaDoTempoAgentes({ etapas }: { etapas: Etapa[] }) {
  return (
    <Timeline defaultValue={etapas.length}>
      {etapas.map((etapa, indice) => (
        <TimelineItem key={indice} step={indice + 1}>
          <TimelineHeader>
            <TimelineDate>{etapa.duracao_ms} ms</TimelineDate>
            <TimelineTitle>{etapa.agente}</TimelineTitle>
          </TimelineHeader>
          <TimelineIndicator />
          <TimelineSeparator />
          <TimelineContent>{etapa.decisao}</TimelineContent>
        </TimelineItem>
      ))}
    </Timeline>
  );
}

/** Uma resposta do GenIA com o painel "Como cheguei a esta resposta" (explicabilidade). */
export function CartaoResposta({ resposta }: { resposta: Resposta }) {
  const [aberto, setAberto] = useState(false);
  const [voto, setVoto] = useState<boolean | null>(null);
  const respondida = resposta.status === "respondida";

  function votar(util: boolean) {
    setVoto(util);
    api("/feedback", { metodo: "POST", corpo: { trace_id: resposta.trace_id, util } }).catch(() => setVoto(null));
  }

  return (
    <article className="grid gap-3 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={respondida ? "primary-light" : "warning-light"}>
          {ROTULOS_STATUS[resposta.status] ?? resposta.status}
        </Badge>
        <SeloValidacao validacao={resposta.validacao} modelo={resposta.modelo} />
        {resposta.uso_fallback && <Badge variant="info-light">Resposta de reserva</Badge>}
        {resposta.pii_mascarada.length > 0 && (
          <Badge variant="outline">Dado pessoal ocultado: {resposta.pii_mascarada.join(", ")}</Badge>
        )}
      </div>

      <TextoComFontes texto={resposta.resposta} fontes={resposta.fontes} />

      {respondida && <p className="border-l-2 pl-3 text-xs text-muted-foreground">{resposta.aviso}</p>}

      <div className="flex flex-wrap items-center gap-2 border-t pt-3">
        <Button variant="ghost" size="sm" onClick={() => setAberto(!aberto)} aria-expanded={aberto}>
          <ChevronDownIcon className={cn("transition-transform", aberto && "rotate-180")} aria-hidden />
          Como cheguei a esta resposta
        </Button>
        <div className="ml-auto flex items-center gap-1">
          <span className="mr-1 text-xs text-muted-foreground">Foi útil?</span>
          <Button
            variant={voto === true ? "secondary" : "ghost"}
            size="icon-sm"
            onClick={() => votar(true)}
            aria-label="Resposta útil"
            aria-pressed={voto === true}
          >
            <ThumbsUpIcon />
          </Button>
          <Button
            variant={voto === false ? "secondary" : "ghost"}
            size="icon-sm"
            onClick={() => votar(false)}
            aria-label="Resposta não útil"
            aria-pressed={voto === false}
          >
            <ThumbsDownIcon />
          </Button>
        </div>
      </div>

      {aberto && (
        <div className="grid gap-5 rounded-lg bg-muted/40 p-4">
          <p className="text-sm">{resposta.explicacao}</p>

          <section className="grid gap-2">
            <h4 className="text-sm font-medium">Etapas executadas</h4>
            <LinhaDoTempoAgentes etapas={resposta.etapas} />
          </section>

          <section className="grid gap-2">
            <h4 className="text-sm font-medium">Trechos do relatório consultados</h4>
            <ListaFontes fontes={resposta.fontes} />
          </section>

          <section className="grid gap-2">
            <h4 className="text-sm font-medium">Verificações do Auditor</h4>
            <ListaChecagens validacao={resposta.validacao} />
            {resposta.validacao.tentativas_reprovadas.map((tentativa) => (
              <p key={tentativa.tentativa} className="text-xs text-muted-foreground">
                Versão {tentativa.tentativa} reprovada: {tentativa.motivos.join("; ")}
              </p>
            ))}
          </section>

          {resposta.validacao.frases.length > 0 && (
            <section className="grid gap-2">
              <h4 className="text-sm font-medium">Apoio de cada frase no relatório</h4>
              <ul className="grid gap-1.5">
                {resposta.validacao.frases.map((frase, indice) => (
                  <li key={indice} className="grid grid-cols-[3rem_1fr] gap-2 text-sm">
                    <span className={cn("font-medium tabular-nums", !frase.apoiada && "text-destructive")}>
                      {Math.round(frase.apoio * 100)}%
                    </span>
                    <span className="text-muted-foreground">{frase.frase}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <dt>Geração</dt>
            <dd>
              {resposta.modelo.modo === "llm"
                ? `${resposta.modelo.provedor} · ${resposta.modelo.modelo}`
                : resposta.modelo.modo === "extrativo"
                  ? "extrativa (frases do próprio relatório, sem LLM)"
                  : "mensagem fixa"}
            </dd>
            <dt>Prompt</dt>
            <dd>{resposta.modelo.prompt_versao}</dd>
            <dt>Base</dt>
            <dd>versão {resposta.modelo.base_versao}</dd>
            <dt>Tempo</dt>
            <dd>{resposta.latencia_ms} ms</dd>
            <dt>Registro</dt>
            <dd className="flex items-center gap-1">
              <code className="truncate">{resposta.trace_id}</code>
              <CopyButton value={resposta.trace_id} size="sm" className="size-6" aria-label="Copiar identificador" />
            </dd>
          </dl>
        </div>
      )}
    </article>
  );
}
