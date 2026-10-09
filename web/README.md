# GenIA — interface web

Interface do GenIA em Next.js, com componentes shadcn/ui, ReUI e Spell UI.

```bash
npm install
npm run dev      # http://localhost:3000 (a API deve estar em http://127.0.0.1:8000)
npm run lint
npm run build
```

| Variável | Para que serve |
|---|---|
| `API_URL` | Endereço da API. Padrão: `http://127.0.0.1:8000`. Na Vercel é preenchida pelo vínculo entre serviços |
| `API_TOKEN` | Opcional: token enviado à API quando ela exige autenticação |

O navegador nunca chama a API diretamente: `app/api/[...caminho]/route.ts` repassa as chamadas.

Telas: `app/page.tsx` (painel), `app/conversa`, `app/monitoramento`, `app/governanca`.
Componentes próprios em `components/genia/`.

Instruções completas no [README do projeto](../README.md).
