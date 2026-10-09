import type { NextRequest } from "next/server";

// Repassa /api/* para a API Python (FastAPI). O navegador fala só com o domínio do front-end:
// a API não precisa ser pública. Na Vercel, API_URL é preenchida pelo vínculo entre os serviços
// (vercel.json); em outra hospedagem, defina API_URL e, se a API exigir, API_TOKEN.
const CABECALHOS_REPASSADOS = ["content-type", "x-sessao", "x-token-operador"];

async function repassar(requisicao: NextRequest, contexto: RouteContext<"/api/[...caminho]">) {
  // Lidas a cada requisição: o vínculo entre serviços só existe em tempo de execução.
  const API_URL = (process.env.API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
  const API_TOKEN = process.env.API_TOKEN;

  const { caminho } = await contexto.params;
  const destino = `${API_URL}/api/${caminho.map(encodeURIComponent).join("/")}${requisicao.nextUrl.search}`;

  const cabecalhos = new Headers();
  for (const nome of CABECALHOS_REPASSADOS) {
    const valor = requisicao.headers.get(nome);
    if (valor) cabecalhos.set(nome, valor);
  }
  if (API_TOKEN) cabecalhos.set("Authorization", `Bearer ${API_TOKEN}`);

  const temCorpo = requisicao.method !== "GET" && requisicao.method !== "HEAD";

  try {
    const resposta = await fetch(destino, {
      method: requisicao.method,
      headers: cabecalhos,
      body: temCorpo ? await requisicao.text() : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
    });
    return new Response(resposta.body, {
      status: resposta.status,
      headers: {
        "content-type": resposta.headers.get("content-type") ?? "application/json",
        "cache-control": "no-store",
      },
    });
  } catch {
    return Response.json(
      { detail: "A API do GenIA está indisponível ou ainda está iniciando. Tente de novo em instantes." },
      { status: 503 },
    );
  }
}

export { repassar as GET, repassar as POST, repassar as DELETE };
