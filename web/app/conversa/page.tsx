"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUpIcon, CircleAlertIcon } from "lucide-react";

import { api, type Nivel, type Resposta } from "@/lib/api";
import { BarsSpinner } from "@/components/bars-spinner";
import { CartaoResposta } from "@/components/genia/resposta";
import { useSessao } from "@/components/genia/sessao";
import { Alert, AlertDescription, AlertTitle } from "@/components/reui/alert";
import { ShimmerText } from "@/components/shimmer-text";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

const SUGESTOES = [
  "Qual é a minha ancestralidade?",
  "Tenho risco de diabetes?",
  "Leite me faz mal?",
  "Posso tomar café à noite?",
  "Esse relatório substitui uma consulta médica?",
];

type Troca = { id: number; pergunta: string; resposta: Resposta | null; erro: string | null };

export default function Conversa() {
  const { consentimento } = useSessao();
  const [nivel, setNivel] = useState<Nivel>("simples");
  const [texto, setTexto] = useState("");
  const [trocas, setTrocas] = useState<Troca[]>([]);
  const [enviando, setEnviando] = useState(false);
  const fim = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [trocas, enviando]);

  async function enviar(pergunta: string) {
    const limpa = pergunta.trim();
    if (!limpa || enviando) return;
    const id = Date.now();
    setTexto("");
    setEnviando(true);
    setTrocas((anteriores) => [...anteriores, { id, pergunta: limpa, resposta: null, erro: null }]);
    try {
      const resposta = await api<Resposta>("/perguntar", { metodo: "POST", corpo: { pergunta: limpa, nivel } });
      setTrocas((anteriores) => anteriores.map((t) => (t.id === id ? { ...t, resposta } : t)));
    } catch (falha) {
      setTrocas((anteriores) => anteriores.map((t) => (t.id === id ? { ...t, erro: (falha as Error).message } : t)));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="grid gap-6">
      <header className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <div className="grid gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">Conversa</h1>
          <p className="text-sm text-muted-foreground">
            Pergunte sobre o que está no relatório. Cada resposta mostra as fontes e como foi verificada.
          </p>
        </div>
        <Tabs value={nivel} onValueChange={(valor) => setNivel(valor as Nivel)} className="ml-auto">
          <TabsList aria-label="Nível de linguagem">
            <TabsTrigger value="simples">Simples</TabsTrigger>
            <TabsTrigger value="tecnico">Técnica</TabsTrigger>
          </TabsList>
        </Tabs>
      </header>

      {trocas.length === 0 && (
        <div className="grid gap-3 rounded-xl border border-dashed p-4">
          <p className="text-sm text-muted-foreground">Comece por uma destas perguntas:</p>
          <div className="flex flex-wrap gap-2">
            {SUGESTOES.map((sugestao) => (
              <Button key={sugestao} variant="outline" size="sm" onClick={() => enviar(sugestao)} disabled={!consentimento?.aceito}>
                {sugestao}
              </Button>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-5" aria-live="polite">
        {trocas.map((troca) => (
          <div key={troca.id} className="grid gap-3">
            <p className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-sm text-primary-foreground">
              {troca.resposta?.pergunta ?? troca.pergunta}
            </p>
            {troca.resposta && <CartaoResposta resposta={troca.resposta} />}
            {troca.erro && (
              <Alert variant="destructive">
                <CircleAlertIcon aria-hidden />
                <AlertTitle>A pergunta não pôde ser respondida</AlertTitle>
                <AlertDescription>{troca.erro}</AlertDescription>
              </Alert>
            )}
            {!troca.resposta && !troca.erro && (
              <div className="flex items-center gap-3 rounded-xl border bg-card p-4">
                <BarsSpinner size={16} />
                <ShimmerText className="text-sm text-muted-foreground">
                  Consultando o relatório e verificando a resposta…
                </ShimmerText>
              </div>
            )}
          </div>
        ))}
        <div ref={fim} />
      </div>

      <form
        className="sticky bottom-20 flex items-end gap-2 rounded-2xl border bg-background p-2 shadow-sm sm:bottom-4"
        onSubmit={(evento) => {
          evento.preventDefault();
          enviar(texto);
        }}
      >
        <Textarea
          value={texto}
          onChange={(evento) => setTexto(evento.target.value)}
          onKeyDown={(evento) => {
            if (evento.key === "Enter" && !evento.shiftKey) {
              evento.preventDefault();
              enviar(texto);
            }
          }}
          placeholder="Escreva sua pergunta sobre o relatório"
          aria-label="Pergunta"
          rows={1}
          maxLength={500}
          className="max-h-32 min-h-9 resize-none border-0 shadow-none focus-visible:ring-0"
        />
        <Button type="submit" size="icon" disabled={!texto.trim() || enviando || !consentimento?.aceito} aria-label="Enviar pergunta">
          <ArrowUpIcon />
        </Button>
      </form>
    </div>
  );
}
