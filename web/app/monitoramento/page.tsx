"use client";

import { useEffect, useState } from "react";
import { CircleAlertIcon, CircleCheckIcon, RefreshCwIcon } from "lucide-react";

import {
  api,
  formatarData,
  ROTULOS_GERACAO,
  ROTULOS_INTENCAO,
  ROTULOS_STATUS,
  type Execucao,
  type Monitoramento,
} from "@/lib/api";
import { useDados } from "@/lib/use-dados";
import { BarsSpinner } from "@/components/bars-spinner";
import { ErroDeCarga, Esqueleto, Indicador, Secao } from "@/components/genia/estados";
import { BarrasHorizontais } from "@/components/genia/graficos";
import { Alert, AlertDescription, AlertTitle } from "@/components/reui/alert";
import { Badge } from "@/components/reui/badge";
import { Button } from "@/components/ui/button";

const NOMES_PIPELINE: Record<string, string> = {
  ingestao: "Ingestão do relatório",
  retencao: "Retenção de registros",
  avaliacao: "Avaliação do modelo",
};

function duracao(segundos: number): string {
  if (segundos < 60) return `${segundos} s`;
  if (segundos < 3600) return `${Math.floor(segundos / 60)} min`;
  return `${Math.floor(segundos / 3600)} h ${Math.floor((segundos % 3600) / 60)} min`;
}

function SeloStatus({ status }: { status: string }) {
  return status === "sucesso" ? (
    <Badge variant="success-light">
      <CircleCheckIcon aria-hidden /> sucesso
    </Badge>
  ) : (
    <Badge variant="destructive-light">
      <CircleAlertIcon aria-hidden /> {status}
    </Badge>
  );
}

function LinhaExecucao({ execucao }: { execucao: Execucao }) {
  return (
    <details className="rounded-lg border bg-card">
      <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 p-3 text-sm">
        <span className="font-medium">{NOMES_PIPELINE[execucao.pipeline] ?? execucao.pipeline}</span>
        <SeloStatus status={execucao.status} />
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          {formatarData(execucao.iniciado_em)} · {execucao.duracao_ms} ms
        </span>
      </summary>
      <div className="overflow-x-auto border-t">
        <table className="w-full min-w-[32rem] text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th className="px-3 py-2 font-normal">Etapa</th>
              <th className="px-3 py-2 font-normal">Situação</th>
              <th className="px-3 py-2 text-right font-normal">Duração</th>
              <th className="px-3 py-2 font-normal">Detalhe</th>
            </tr>
          </thead>
          <tbody>
            {execucao.etapas.map((etapa) => (
              <tr key={etapa.etapa} className="border-t align-top">
                <td className="px-3 py-2 font-mono text-xs">{etapa.etapa}</td>
                <td className="px-3 py-2">
                  <SeloStatus status={etapa.status} />
                </td>
                <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                  {etapa.duracao_ms === undefined ? "—" : `${etapa.duracao_ms} ms`}
                </td>
                <td className="px-3 py-2 text-muted-foreground">{etapa.detalhe}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function ReexecutarPipeline({ aoConcluir }: { aoConcluir: () => void }) {
  const [token, setToken] = useState("");
  const [executando, setExecutando] = useState(false);
  const [mensagem, setMensagem] = useState<{ erro: boolean; texto: string } | null>(null);

  async function executar() {
    setExecutando(true);
    setMensagem(null);
    try {
      const resultado = await api<Execucao>("/pipeline/ingestao", { metodo: "POST", tokenOperador: token });
      setMensagem({ erro: resultado.status !== "sucesso", texto: `Pipeline concluído: ${resultado.status} em ${resultado.duracao_ms} ms.` });
      aoConcluir();
    } catch (falha) {
      setMensagem({ erro: true, texto: (falha as Error).message });
    } finally {
      setExecutando(false);
    }
  }

  return (
    <form
      className="grid gap-2 rounded-lg border bg-card p-3"
      onSubmit={(evento) => {
        evento.preventDefault();
        executar();
      }}
    >
      <label htmlFor="token" className="text-sm font-medium">
        Reexecutar a ingestão (reindexa o relatório)
      </label>
      <div className="flex flex-wrap gap-2">
        <input
          id="token"
          type="password"
          value={token}
          onChange={(evento) => setToken(evento.target.value)}
          placeholder="Token de operador"
          autoComplete="off"
          className="h-8 min-w-0 flex-1 rounded-lg border bg-background px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button type="submit" variant="outline" disabled={!token || executando}>
          {executando && <BarsSpinner size={14} />}
          Executar
        </Button>
      </div>
      {mensagem && (
        <p className={mensagem.erro ? "text-sm text-destructive" : "text-sm text-muted-foreground"} role="status">
          {mensagem.texto}
        </p>
      )}
    </form>
  );
}

export default function PaginaMonitoramento() {
  const { dados, erro, carregando, recarregar } = useDados<Monitoramento>("/monitoramento");

  // Atualiza sozinho a cada 20 segundos enquanto a página está aberta.
  useEffect(() => {
    const intervalo = window.setInterval(recarregar, 20_000);
    return () => window.clearInterval(intervalo);
  }, [recarregar]);

  if (erro && !dados) return <ErroDeCarga mensagem={erro} aoTentar={recarregar} />;
  if (!dados) return <Esqueleto linhas={8} />;

  const { saude, metricas } = dados;
  const saudavel = saude.status === "ok";
  const respondidas = metricas.por_status.respondida ?? 0;

  return (
    <div className="grid gap-8">
      <header className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <div className="grid gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Monitoramento</h1>
          <p className="text-sm text-muted-foreground">
            Pipelines, automações e comportamento do agente, a partir do registro de auditoria. Nenhum texto de
            pergunta ou resposta aparece aqui.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={recarregar} disabled={carregando} className="ml-auto">
          <RefreshCwIcon className={carregando ? "animate-spin" : undefined} aria-hidden /> Atualizar
        </Button>
      </header>

      <Alert variant={saudavel ? "success" : "warning"}>
        {saudavel ? <CircleCheckIcon aria-hidden /> : <CircleAlertIcon aria-hidden />}
        <AlertTitle>{saudavel ? "Sistema operacional" : "Sistema degradado"}</AlertTitle>
        <AlertDescription>
          <p>
            Versão {saude.versao} · no ar há {duracao(saude.ativo_ha_segundos)} · base {saude.base_versao ?? "indisponível"} ·
            prompt {saude.prompt_versao} · geração:{" "}
            {saude.llm.modelo ? `${saude.llm.provedor} (${saude.llm.modelo})` : "extrativa, sem LLM configurado"}
          </p>
          {saude.ingestao.erro && <p>Falha na ingestão: {saude.ingestao.erro}</p>}
        </AlertDescription>
      </Alert>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Indicador rotulo="Perguntas processadas" valor={String(metricas.total_interacoes)} nota={`${respondidas} respondidas`} />
        <Indicador
          rotulo="Latência mediana"
          valor={`${metricas.latencia_ms.p50} ms`}
          nota={`percentil 95: ${metricas.latencia_ms.p95} ms`}
        />
        <Indicador
          rotulo="Reprovadas pelo Auditor"
          valor={String(metricas.respostas_reprovadas_na_auditoria)}
          nota={`${metricas.uso_fallback} trocadas pela resposta de reserva`}
        />
        <Indicador
          rotulo="Execuções de pipeline"
          valor={String(metricas.execucoes.total)}
          nota={metricas.execucoes.falhas === 0 ? "nenhuma falha" : `${metricas.execucoes.falhas} com falha`}
        />
      </div>

      <div className="grid gap-8 md:grid-cols-2">
        <Secao titulo="Desfecho das perguntas" descricao="Quantas foram respondidas, recusadas ou bloqueadas.">
          <div className="rounded-xl border bg-card p-4">
            <BarrasHorizontais
              dados={Object.entries(metricas.por_status)
                .map(([status, valor]) => ({ rotulo: ROTULOS_STATUS[status] ?? status, valor }))
                .sort((a, b) => b.valor - a.valor)}
            />
          </div>
        </Secao>
        <Secao titulo="Intenção identificada" descricao="Classificação feita pelo agente de Triagem.">
          <div className="rounded-xl border bg-card p-4">
            <BarrasHorizontais
              dados={Object.entries(metricas.por_intencao)
                .map(([rotulo, valor]) => ({ rotulo: ROTULOS_INTENCAO[rotulo] ?? rotulo, valor }))
                .sort((a, b) => b.valor - a.valor)}
            />
          </div>
        </Secao>
      </div>

      <Secao titulo="Execuções de pipeline" descricao="Cada execução registra suas etapas; abra uma linha para ver o detalhe.">
        <div className="grid gap-2">
          {dados.execucoes.map((execucao) => (
            <LinhaExecucao key={execucao.id} execucao={execucao} />
          ))}
          <ReexecutarPipeline aoConcluir={recarregar} />
        </div>
      </Secao>

      <Secao titulo="Últimas interações" descricao="Somente metadados: o rastro de cada resposta, sem o conteúdo.">
        {dados.ultimas_interacoes.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma interação registrada ainda.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border bg-card">
            <table className="w-full min-w-[44rem] text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground">
                  <th className="px-3 py-2 font-normal">Quando</th>
                  <th className="px-3 py-2 font-normal">Desfecho</th>
                  <th className="px-3 py-2 font-normal">Intenção</th>
                  <th className="px-3 py-2 font-normal">Agentes</th>
                  <th className="px-3 py-2 font-normal">Geração</th>
                  <th className="px-3 py-2 text-right font-normal">Tempo</th>
                </tr>
              </thead>
              <tbody>
                {dados.ultimas_interacoes.map((interacao) => (
                  <tr key={interacao.trace_id} className="border-t">
                    <td className="px-3 py-2 whitespace-nowrap tabular-nums">{formatarData(interacao.criado_em)}</td>
                    <td className="px-3 py-2">
                      {interacao.tipo === "resumo" ? "Resumo automático" : (ROTULOS_STATUS[interacao.status] ?? interacao.status)}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {interacao.intencao ? (ROTULOS_INTENCAO[interacao.intencao] ?? interacao.intencao) : "—"}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{interacao.etapas.map((e) => e.agente).join(" → ")}</td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {interacao.modelo ?? ROTULOS_GERACAO[interacao.provedor ?? ""] ?? interacao.provedor}
                      {interacao.uso_fallback && " (reserva)"}
                    </td>
                    <td className="px-3 py-2 text-right whitespace-nowrap tabular-nums">{interacao.latencia_ms} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Secao>

      <Secao titulo="Eventos" descricao="Consentimentos, exclusões de dados e uso da resposta de reserva.">
        {dados.eventos.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhum evento registrado ainda.</p>
        ) : (
          <ul className="grid gap-1.5">
            {dados.eventos.map((evento) => (
              <li key={evento.id} className="flex flex-wrap items-baseline gap-x-3 text-sm">
                <span className="text-xs text-muted-foreground tabular-nums">{formatarData(evento.criado_em)}</span>
                <span className="font-mono text-xs">{evento.tipo}</span>
                <span className="text-muted-foreground">
                  {Object.entries(evento.detalhe)
                    .filter(([chave]) => chave !== "trace_id")
                    .map(([chave, valor]) => `${chave}: ${String(valor)}`)
                    .join(" · ")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Secao>
    </div>
  );
}
