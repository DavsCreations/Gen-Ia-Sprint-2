import type { MetadataRoute } from "next";

// Manifesto de aplicativo web: permite instalar o GenIA na tela inicial do celular.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "GenIA — Assistente para Relatórios Genéticos",
    short_name: "GenIA",
    description: "Explica relatórios genéticos com fontes, validação e rastreabilidade.",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#ffffff",
    lang: "pt-BR",
    icons: [{ src: "/icone.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
