import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { Casca } from "@/components/genia/casca";
import { ProvedorSessao } from "@/components/genia/sessao";
import { TooltipProvider } from "@/components/ui/tooltip";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: { default: "GenIA", template: "%s · GenIA" },
  description: "Assistente que explica relatórios genéticos com fontes, validação e rastreabilidade.",
  applicationName: "GenIA",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#ffffff",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full">
        <TooltipProvider>
          <ProvedorSessao>
            <Casca>{children}</Casca>
          </ProvedorSessao>
        </TooltipProvider>
      </body>
    </html>
  );
}
