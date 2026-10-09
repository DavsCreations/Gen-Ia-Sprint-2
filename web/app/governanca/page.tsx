"use client";

import { useState } from "react";
import { CheckIcon, DownloadIcon, Trash2Icon, XIcon } from "lucide-react";

import { api, formatarData, formatarPercentual, renovarSessao, type ResultadoAvaliacao } from "@/lib/api";
import { useDados } from "@/lib/use-dados";
import { ErroDeCarga, Esqueleto, Secao } from "@/components/genia/estados";
import { useSessao } from "@/components/genia/sessao";
import { Badge } from "@/components/reui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

type Exportacao = { sessao: string; interacoes: unknown[]; eventos: unknown[] };

function MeusDados() {
  const { consentimento, aceitar, recarregar } = useSessao();
  const [mensagem, setMensagem] = useState<string | null>(null);

  async function exportar() {
    try {
      const dados = await api<Exportacao>("/meus-dados");
      const url = URL.createObjectURL(new Blob([JSON.stringify(dados, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "genia-meus-dados.json";
      link.click();
      URL.revokeObjectURL(url);
      setMensagem(`Arquivo gerado com ${dados.interacoes.length} interação(ões) e ${dados.eventos.length} evento(s).`);
    } catch (falha) {
      setMensagem((falha as Error).message);
    }
  }

  async function apagar() {
    try {
      const resultado = await api<{ interacoes_apagadas: number }>("/meus-dados", { metodo: "DELETE" });
      // Descarta também o identificador guardado no navegador: a próxima visita é uma sessão nova.
      renovarSessao();
      recarregar();
      setMensagem(`Dados apagados: ${resultado.interacoes_apagadas} interação(ões), além do consentimento e dos eventos.`);
    } catch (falha) {
      setMensagem((falha as Error).message);
    }
  }

  return (
    <div className="grid gap-4 rounded-xl border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span>Termo de uso e privacidade (versão {consentimento?.versao_termo ?? "—"}):</span>
        {consentimento?.aceito ? <Badge variant="success-light">aceito</Badge> : <Badge variant="outline">não aceito</Badge>}
      </div>

      <div className="flex items-start gap-3">
        <Switch
          id="guardar-conteudo"
          checked={consentimento?.guardar_conteudo ?? false}
          disabled={!consentimento?.aceito}
          onCheckedChange={(valor) => aceitar(valor)}
        />
        <Label htmlFor="guardar-conteudo" className="grid gap-1 leading-snug font-normal">
          <span className="font-medium">Guardar o texto das minhas perguntas e respostas</span>
          <span className="text-muted-foreground">
            Desligado, o registro guarda só metadados. Vale para as próximas perguntas; o que já foi gravado pode ser
            apagado abaixo.
          </span>
        </Label>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={exportar}>
          <DownloadIcon aria-hidden /> Exportar meus dados
        </Button>
        <Dialog>
          <DialogTrigger render={<Button variant="destructive" />}>
            <Trash2Icon aria-hidden /> Apagar meus dados
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Apagar todos os seus dados?</DialogTitle>
              <DialogDescription>
                Suas interações, eventos e o consentimento serão removidos do registro. Não é possível desfazer. Para
                continuar usando o GenIA será preciso aceitar o termo de novo.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <DialogClose render={<Button variant="outline" />}>Cancelar</DialogClose>
              <DialogClose render={<Button variant="destructive" onClick={apagar} />}>Apagar definitivamente</DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {mensagem && (
        <p className="text-sm text-muted-foreground" role="status">
          {mensagem}
        </p>
      )}
    </div>
  );
}

const TRATAMENTO = [
  ["Finalidade", "Explicar o relatório genético ao próprio titular. Não há diagnóstico, prescrição nem decisão automatizada."],
  ["Base legal", "Consentimento específico e destacado do titular (LGPD, art. 11, I), por se tratar de dado genético, que é dado pessoal sensível."],
  ["Minimização", "A identificação do paciente não é indexada nem enviada ao modelo de linguagem. CPF, e-mail, telefone e datas digitados na pergunta são mascarados antes de qualquer processamento."],
  ["Registro (logging)", "Cada resposta gera um registro com identificador, fontes usadas, versão do modelo e do prompt, resultado das verificações e tempo. A sessão é gravada como pseudônimo."],
  ["Retenção", "Os registros são apagados automaticamente após o prazo de retenção. O titular pode apagar tudo antes disso."],
  ["Explicabilidade", "Toda resposta traz \"Como cheguei a esta resposta\": etapas, trechos consultados, pontuações e verificações."],
  ["Revisão humana", "Qualquer orientação de saúde depende de um profissional. O sistema recusa pedidos de medicamento, dose, tratamento ou diagnóstico."],
];

function nomeDoCriterio(criterio: string): string {
  return (
    {
      recuperacao_acerto_top3: "Trecho correto entre os 3 primeiros",
      pipeline_acuracia_status: "Comportamento correto ponta a ponta",
      pipeline_vazamentos: "Pedidos de conselho médico respondidos",
      validador_defeitos_detectados: "Defeitos detectados pelo validador",
      validador_falsas_reprovacoes_max: "Respostas corretas reprovadas",
    }[criterio] ?? criterio
  );
}

function Avaliacao() {
  const { dados, erro, recarregar } = useDados<Record<string, ResultadoAvaliacao>>("/avaliacao");
  if (erro) return <ErroDeCarga mensagem={erro} aoTentar={recarregar} />;
  if (!dados) return <Esqueleto linhas={5} />;

  const modos = Object.entries(dados).filter(([nome]) => nome !== "antes_dos_ajustes");
  const [, principal] = modos.find(([nome]) => nome !== "extrativo") ?? modos[0];
  const original = principal.recuperacao[0];
  const final = principal.recuperacao[principal.recuperacao.length - 1];
  const verificacao = principal.pipeline.acuracia_por_particao.verificacao;

  return (
    <div className="grid gap-4">
      <div className="overflow-x-auto rounded-xl border bg-card">
        <table className="w-full min-w-[30rem] text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th className="px-3 py-2 font-normal">Critério mínimo</th>
              <th className="px-3 py-2 text-right font-normal">Exigido</th>
              <th className="px-3 py-2 text-right font-normal">Obtido</th>
              <th className="px-3 py-2 font-normal">Situação</th>
            </tr>
          </thead>
          <tbody>
            {principal.criterios.map((criterio) => {
              const proporcao = criterio.minimo > 0 && criterio.minimo <= 1 && !criterio.criterio.endsWith("_max");
              return (
                <tr key={criterio.criterio} className="border-t">
                  <td className="px-3 py-2">{nomeDoCriterio(criterio.criterio)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {proporcao ? `≥ ${formatarPercentual(criterio.minimo, 0)}` : `≤ ${criterio.minimo}`}
                  </td>
                  <td className="px-3 py-2 text-right font-medium tabular-nums">
                    {proporcao ? formatarPercentual(criterio.obtido) : criterio.obtido}
                  </td>
                  <td className="px-3 py-2">
                    {criterio.ok ? (
                      <span className="inline-flex items-center gap-1">
                        <CheckIcon className="size-4 text-success" aria-hidden /> atendido
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1">
                        <XIcon className="size-4 text-destructive" aria-hidden /> não atendido
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-sm text-muted-foreground">
        Avaliação de {formatarData(principal.gerado_em)}, modo <code>{principal.modo}</code>, com {principal.perguntas} perguntas.
        A busca acerta o trecho em 1º lugar em {formatarPercentual(final.acerto_top1)} dos casos (era{" "}
        {formatarPercentual(original.acerto_top1)} na versão da Sprint 2).
        {verificacao !== undefined &&
          ` Em perguntas novas, nunca usadas para ajustar o sistema, o comportamento foi correto em ${formatarPercentual(verificacao)}.`}{" "}
        O relatório completo, com as falhas restantes, está em <code>docs/avaliacao.md</code>.
      </p>
    </div>
  );
}

export default function Governanca() {
  return (
    <div className="grid gap-10">
      <header className="grid gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Privacidade e governança</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          O que o GenIA faz com os seus dados, como exercer seus direitos e como a qualidade das respostas é medida.
        </p>
      </header>

      <Secao titulo="Seus dados" descricao="Direitos de acesso e de eliminação (LGPD, art. 18).">
        <MeusDados />
      </Secao>

      <Secao titulo="Como seus dados são tratados" descricao="Resumo da política de governança (docs/governanca.md).">
        <dl className="grid gap-3 rounded-xl border bg-card p-4">
          {TRATAMENTO.map(([termo, descricao]) => (
            <div key={termo} className="grid gap-0.5 sm:grid-cols-[10rem_1fr] sm:gap-4">
              <dt className="text-sm font-medium">{termo}</dt>
              <dd className="text-sm text-muted-foreground">{descricao}</dd>
            </div>
          ))}
        </dl>
      </Secao>

      <Secao titulo="Qualidade medida" descricao="Critérios que a solução precisa atingir a cada mudança; abaixo deles, a entrega é bloqueada.">
        <Avaliacao />
      </Secao>
    </div>
  );
}
