"use client";

import { useState } from "react";
import Link from "next/link";
import { InfoIcon, MessageCircleIcon } from "lucide-react";

import { type ItemTema, type Nivel, type Relatorio, type Resumo } from "@/lib/api";
import { useDados } from "@/lib/use-dados";
import { BlurReveal } from "@/components/blur-reveal";
import { ErroDeCarga, Esqueleto, Secao } from "@/components/genia/estados";
import { GraficoAncestralidade, MedidorDeRisco } from "@/components/genia/graficos";
import { SeloValidacao, TextoComFontes } from "@/components/genia/resposta";
import { useSessao } from "@/components/genia/sessao";
import { Alert, AlertDescription, AlertTitle } from "@/components/reui/alert";
import { Badge } from "@/components/reui/badge";
import { ShimmerText } from "@/components/shimmer-text";
import { buttonVariants } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

function CartaoTema({ item, nivel }: { item: ItemTema; nivel: Nivel }) {
  return (
    <article className="grid content-start gap-3 rounded-xl border bg-card p-4">
      <div className="grid gap-1">
        <h3 className="font-medium">{item.tema}</h3>
        <p className="text-sm text-muted-foreground">{item.resultado}</p>
      </div>
      {item.nivel_risco && <MedidorDeRisco nivel={item.nivel_risco} />}
      <p className="text-sm leading-relaxed">{nivel === "simples" ? item.explicacao_simples : item.explicacao_tecnica}</p>
      <p className="border-l-2 pl-3 text-sm text-muted-foreground">
        <span className="font-medium text-foreground">Recomendação do relatório: </span>
        {item.recomendacao}
      </p>
    </article>
  );
}

function ResumoAutomatico({ nivel }: { nivel: Nivel }) {
  const { consentimento } = useSessao();
  const { dados, erro, carregando, recarregar } = useDados<Resumo>(`/resumo?nivel=${nivel}`, !!consentimento?.aceito);

  if (!consentimento?.aceito) {
    return <p className="text-sm text-muted-foreground">O resumo aparece depois do aceite do termo de privacidade.</p>;
  }
  if (erro) return <ErroDeCarga mensagem={erro} aoTentar={recarregar} />;
  if (carregando || !dados) {
    return (
      <div className="grid gap-3">
        <ShimmerText className="text-sm text-muted-foreground">Resumindo o relatório…</ShimmerText>
        <Esqueleto linhas={4} />
      </div>
    );
  }
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <SeloValidacao validacao={dados.validacao} modelo={dados.modelo} />
        <Badge variant="outline">
          {dados.modelo.modo === "llm" ? `Gerado por ${dados.modelo.modelo}` : "Montado com frases do relatório"}
        </Badge>
      </div>
      <TextoComFontes texto={dados.resumo} fontes={dados.fontes} />
      <p className="border-l-2 pl-3 text-xs text-muted-foreground">{dados.aviso}</p>
    </div>
  );
}

export default function Painel() {
  const [nivel, setNivel] = useState<Nivel>("simples");
  const { dados: relatorio, erro, carregando, recarregar } = useDados<Relatorio>("/relatorio");

  return (
    <div className="grid gap-10">
      <header className="grid gap-4">
        <BlurReveal as="h1" className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          Seu relatório genético, explicado
        </BlurReveal>
        <p className="max-w-2xl text-muted-foreground">
          Cada explicação vem do próprio relatório, cita a fonte e passa por uma verificação automática antes de
          aparecer. O GenIA não faz diagnóstico.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/conversa" className={buttonVariants({ size: "lg" })}>
            <MessageCircleIcon aria-hidden /> Perguntar sobre o relatório
          </Link>
          <Tabs value={nivel} onValueChange={(valor) => setNivel(valor as Nivel)}>
            <TabsList aria-label="Nível de linguagem">
              <TabsTrigger value="simples">Linguagem simples</TabsTrigger>
              <TabsTrigger value="tecnico">Linguagem técnica</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
        {relatorio && (
          <p className="text-xs text-muted-foreground">
            {relatorio.tipo_relatorio} · {relatorio.id_relatorio} · emitido em{" "}
            {new Date(`${relatorio.data_emissao}T12:00:00`).toLocaleDateString("pt-BR")}
          </p>
        )}
      </header>

      <Secao titulo="Resumo automático" descricao="Visão geral do relatório, no nível de linguagem escolhido acima.">
        <div className="rounded-xl border bg-card p-4">
          <ResumoAutomatico nivel={nivel} />
        </div>
      </Secao>

      {erro && <ErroDeCarga mensagem={erro} aoTentar={recarregar} />}
      {carregando && !relatorio && <Esqueleto linhas={6} />}

      {relatorio && (
        <>
          <Secao titulo="Ancestralidade" descricao={relatorio.ancestralidade.resumo}>
            <div className="rounded-xl border bg-card p-4">
              <GraficoAncestralidade composicao={relatorio.ancestralidade.composicao} />
            </div>
          </Secao>

          <Secao
            titulo="Saúde genética"
            descricao="Predisposição indica possibilidade, não certeza: hábitos e histórico familiar também contam."
          >
            <div className="grid gap-3 md:grid-cols-3">
              {relatorio.saude_genetica.map((item) => (
                <CartaoTema key={item.tema} item={item} nivel={nivel} />
              ))}
            </div>
          </Secao>

          <Secao titulo="Bem-estar">
            <div className="grid gap-3 md:grid-cols-3">
              {relatorio.bem_estar.map((item) => (
                <CartaoTema key={item.tema} item={item} nivel={nivel} />
              ))}
            </div>
          </Secao>

          <Alert variant="info">
            <InfoIcon aria-hidden />
            <AlertTitle>Limites deste relatório</AlertTitle>
            <AlertDescription>
              <ul className="grid list-disc gap-1 pl-4">
                {relatorio.disclaimers.map((aviso) => (
                  <li key={aviso}>{aviso}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        </>
      )}
    </div>
  );
}
