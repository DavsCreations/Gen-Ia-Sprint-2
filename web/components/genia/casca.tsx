"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ActivityIcon, DnaIcon, LayoutDashboardIcon, MessageCircleIcon, ShieldCheckIcon } from "lucide-react";

import { cn } from "@/lib/utils";

const ROTAS = [
  { href: "/", rotulo: "Painel", Icone: LayoutDashboardIcon },
  { href: "/conversa", rotulo: "Conversa", Icone: MessageCircleIcon },
  { href: "/monitoramento", rotulo: "Monitoramento", Icone: ActivityIcon },
  { href: "/governanca", rotulo: "Privacidade", Icone: ShieldCheckIcon },
];

/** Cabeçalho com navegação no desktop e barra inferior no celular. */
export function Casca({ children }: { children: React.ReactNode }) {
  const caminho = usePathname();

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center gap-6 px-4">
          <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid size-7 place-items-center rounded-lg bg-primary text-primary-foreground">
              <DnaIcon className="size-4" aria-hidden />
            </span>
            GenIA
          </Link>
          <nav className="hidden items-center gap-1 sm:flex" aria-label="Principal">
            {ROTAS.map(({ href, rotulo }) => (
              <Link
                key={href}
                href={href}
                aria-current={caminho === href ? "page" : undefined}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground",
                  caminho === href && "bg-muted font-medium text-foreground",
                )}
              >
                {rotulo}
              </Link>
            ))}
          </nav>
          <span className="ml-auto hidden text-xs text-muted-foreground md:block">
            Relatório simulado · uso educacional
          </span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 pt-6 pb-24 sm:pb-10">{children}</main>

      <nav
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden"
        aria-label="Principal"
      >
        {ROTAS.map(({ href, rotulo, Icone }) => (
          <Link
            key={href}
            href={href}
            aria-current={caminho === href ? "page" : undefined}
            className={cn(
              "flex flex-col items-center gap-1 py-2 text-[0.7rem] text-muted-foreground",
              caminho === href && "font-medium text-foreground",
            )}
          >
            <Icone className="size-5" aria-hidden />
            {rotulo}
          </Link>
        ))}
      </nav>
    </div>
  );
}
