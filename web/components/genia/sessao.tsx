"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import Link from "next/link";
import { ShieldCheckIcon } from "lucide-react";

import { api, type Consentimento } from "@/lib/api";
import { BarsSpinner } from "@/components/bars-spinner";
import { Alert, AlertDescription, AlertTitle } from "@/components/reui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

type Contexto = {
  consentimento: Consentimento | null;
  erro: string | null;
  aceitar: (guardarConteudo: boolean) => Promise<void>;
  recarregar: () => void;
};

const ContextoSessao = createContext<Contexto | null>(null);

export function useSessao(): Contexto {
  const contexto = useContext(ContextoSessao);
  if (!contexto) throw new Error("useSessao deve ser usado dentro de ProvedorSessao");
  return contexto;
}

/**
 * Mantém o estado do consentimento e exibe o termo antes de qualquer uso.
 * Nenhuma pergunta ou resumo é processado sem o aceite: a API também recusa (403).
 */
export function ProvedorSessao({ children }: { children: React.ReactNode }) {
  const [consentimento, setConsentimento] = useState<Consentimento | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [guardar, setGuardar] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    let ativo = true;
    api<Consentimento>("/consentimento")
      .then((dados) => {
        if (!ativo) return;
        setConsentimento(dados);
        setErro(null);
      })
      .catch((falha: Error) => ativo && setErro(falha.message));
    return () => {
      ativo = false;
    };
  }, [versao]);

  const aceitar = useCallback(async (guardarConteudo: boolean) => {
    setEnviando(true);
    try {
      setConsentimento(
        await api<Consentimento>("/consentimento", { metodo: "POST", corpo: { guardar_conteudo: guardarConteudo } }),
      );
      setErro(null);
    } catch (falha) {
      setErro((falha as Error).message);
    } finally {
      setEnviando(false);
    }
  }, []);

  const recarregar = useCallback(() => setVersao((v) => v + 1), []);
  const precisaAceitar = consentimento !== null && !consentimento.aceito;

  return (
    <ContextoSessao.Provider value={{ consentimento, erro, aceitar, recarregar }}>
      {children}

      <Dialog open={precisaAceitar} onOpenChange={() => undefined}>
        <DialogContent showCloseButton={false} className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <ShieldCheckIcon className="size-4" aria-hidden />
              Antes de começar: uso dos seus dados
            </DialogTitle>
            <DialogDescription>
              O GenIA explica um relatório genético. Dado genético é dado pessoal sensível pela LGPD, por isso
              precisamos do seu consentimento.
            </DialogDescription>
          </DialogHeader>

          <ul className="grid gap-2 text-sm text-muted-foreground">
            <li>
              <strong className="text-foreground">O que é processado:</strong> suas perguntas e os trechos do
              relatório usados para respondê-las.
            </li>
            <li>
              <strong className="text-foreground">Para quê:</strong> somente para explicar o relatório a você. Não
              há diagnóstico nem decisão automatizada sobre a sua saúde.
            </li>
            <li>
              <strong className="text-foreground">O que fica registrado:</strong> metadados de cada resposta
              (horário, fontes usadas, resultado das verificações), ligados a um identificador anônimo, por até{" "}
              {consentimento?.retencao_dias ?? 30} dias.
            </li>
            <li>
              <strong className="text-foreground">Seus direitos:</strong> ver, exportar e apagar tudo a qualquer
              momento em <Link href="/governanca" className="underline underline-offset-2">Privacidade</Link>.
            </li>
          </ul>

          <div className="flex items-start gap-3 rounded-lg border p-3">
            <Switch id="guardar" checked={guardar} onCheckedChange={setGuardar} />
            <Label htmlFor="guardar" className="grid gap-1 leading-snug font-normal">
              <span className="font-medium">Guardar também o texto das minhas perguntas e respostas (opcional)</span>
              <span className="text-muted-foreground">
                Ajuda a auditar a qualidade das respostas. Sem isso, o texto não é gravado.
              </span>
            </Label>
          </div>

          {erro && (
            <Alert variant="destructive">
              <AlertTitle>Não foi possível registrar o aceite</AlertTitle>
              <AlertDescription>{erro}</AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            <Button onClick={() => aceitar(guardar)} disabled={enviando} className="w-full sm:w-auto">
              {enviando && <BarsSpinner size={14} />}
              Li e aceito
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ContextoSessao.Provider>
  );
}
