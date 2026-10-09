// Cliente da API do GenIA e tipos dos dados trocados com ela.

export type Nivel = "simples" | "tecnico";

export type Fonte = {
  id: string;
  secao: string;
  tema: string;
  texto: string;
  score: number;
  score_semantico: number;
  score_lexical: number;
  usada_no_contexto: boolean;
};

export type Checagem = {
  nome: string;
  ok: boolean;
  bloqueante: boolean;
  valor: unknown;
  detalhe: string;
};

export type Frase = { frase: string; apoio: number; fonte: string; apoiada: boolean };

export type Validacao = {
  aprovada: boolean;
  checagens: Checagem[];
  frases: Frase[];
  tentativas_reprovadas: { tentativa: number; motivos: string[] }[];
};

export type Etapa = {
  agente: string;
  duracao_ms: number;
  decisao: string;
  detalhes?: Record<string, unknown>;
};

export type Modelo = {
  modo: "llm" | "extrativo" | "mensagem_fixa";
  provedor: string;
  modelo: string | null;
  prompt_versao: string;
  embedding?: string;
  base_versao: string;
};

export type Resposta = {
  trace_id: string;
  pergunta: string;
  resposta: string;
  aviso: string;
  nivel: Nivel;
  status: string;
  intencao: { rotulo: string; confianca: number; origem: string };
  fontes: Fonte[];
  validacao: Validacao;
  etapas: Etapa[];
  explicacao: string;
  modelo: Modelo;
  uso_fallback: boolean;
  pii_mascarada: string[];
  latencia_ms: number;
};

export type Resumo = {
  trace_id: string;
  resumo: string;
  aviso: string;
  nivel: Nivel;
  fontes: { id: string; tema: string; secao: string }[];
  validacao: Validacao;
  modelo: Modelo;
  latencia_ms: number;
  em_cache: boolean;
};

export type ItemComposicao = { origem: string; percentual: number; explicacao: string };

export type ItemTema = {
  tema: string;
  resultado: string;
  nivel_risco?: string;
  explicacao_tecnica: string;
  explicacao_simples: string;
  recomendacao: string;
};

export type Relatorio = {
  id_relatorio: string;
  tipo_relatorio: string;
  data_emissao: string;
  ancestralidade: { resumo: string; composicao: ItemComposicao[] };
  saude_genetica: ItemTema[];
  bem_estar: ItemTema[];
  disclaimers: string[];
};

export type Consentimento = {
  aceito: boolean;
  guardar_conteudo: boolean;
  versao_termo: string;
  retencao_dias: number;
};

export type Saude = {
  status: "ok" | "degradado";
  versao: string;
  ativo_ha_segundos: number;
  ingestao: { status: string | null; erro: string | null; duracao_ms: number | null };
  base_versao: string | null;
  llm: { provedor: string; modelo: string | null };
  prompt_versao: string;
  registro: "postgres" | "sqlite";
};

export type EtapaPipeline = { etapa: string; status: string; detalhe: string; duracao_ms?: number };

export type Execucao = {
  id: number;
  pipeline: string;
  iniciado_em: string;
  duracao_ms: number;
  status: string;
  etapas: EtapaPipeline[];
  erro: string | null;
};

export type Monitoramento = {
  saude: Saude;
  metricas: {
    total_interacoes: number;
    por_status: Record<string, number>;
    por_intencao: Record<string, number>;
    por_dia: Record<string, number>;
    latencia_ms: { p50: number; p95: number; max: number };
    uso_fallback: number;
    respostas_reprovadas_na_auditoria: number;
    feedback: { avaliadas: number; uteis: number };
    execucoes: { total: number; falhas: number };
  };
  execucoes: Execucao[];
  eventos: { id: number; criado_em: string; tipo: string; detalhe: Record<string, unknown> }[];
  ultimas_interacoes: {
    trace_id: string;
    criado_em: string;
    tipo: string;
    intencao: string | null;
    status: string;
    provedor: string | null;
    modelo: string | null;
    prompt_versao: string;
    uso_fallback: boolean;
    latencia_ms: number;
    aprovada: boolean;
    fontes: string[];
    etapas: Etapa[];
  }[];
};

export type ResultadoAvaliacao = {
  gerado_em: string;
  modo: string;
  perguntas: number;
  recuperacao: {
    configuracao: string;
    acerto_top1: number;
    acerto_top3: number;
    mrr: number;
    separacao_auc: number;
  }[];
  intencao: { validacao_cruzada: { acuracia: number; f1_macro: number } };
  validador: {
    defeitos_detectados: number;
    total_com_defeito: number;
    falsas_reprovacoes: number;
    total_corretas: number;
  };
  pipeline: {
    acuracia_status: number;
    acuracia_por_particao: Record<string, number>;
    vazamentos: string[];
    respondidas: {
      fonte_correta: number | null;
      fatos_presentes: number | null;
      apoio_medio: number;
      flesch_medio: number | null;
    };
  };
  consistencia: { repeticao: { similaridade_media: number }; parafrases: { similaridade_media: number } };
  criterios: { criterio: string; minimo: number; obtido: number; ok: boolean }[];
};

export class ErroApi extends Error {
  constructor(
    mensagem: string,
    public status: number,
  ) {
    super(mensagem);
  }
}

const CHAVE_SESSAO = "genia.sessao";

/** Identificador aleatório da sessão, guardado só neste navegador. A API grava apenas um pseudônimo dele. */
export function obterSessao(): string {
  let sessao = window.localStorage.getItem(CHAVE_SESSAO);
  if (!sessao) {
    sessao = crypto.randomUUID();
    window.localStorage.setItem(CHAVE_SESSAO, sessao);
  }
  return sessao;
}

export function renovarSessao(): void {
  window.localStorage.removeItem(CHAVE_SESSAO);
}

export async function api<T>(
  caminho: string,
  opcoes: { metodo?: "GET" | "POST" | "DELETE"; corpo?: unknown; tokenOperador?: string } = {},
): Promise<T> {
  const cabecalhos: Record<string, string> = { "X-Sessao": obterSessao() };
  if (opcoes.corpo !== undefined) cabecalhos["Content-Type"] = "application/json";
  if (opcoes.tokenOperador) cabecalhos["X-Token-Operador"] = opcoes.tokenOperador;

  let resposta: Response;
  try {
    resposta = await fetch(`/api${caminho}`, {
      method: opcoes.metodo ?? "GET",
      headers: cabecalhos,
      body: opcoes.corpo === undefined ? undefined : JSON.stringify(opcoes.corpo),
      cache: "no-store",
    });
  } catch {
    throw new ErroApi("Não foi possível falar com o servidor. Verifique sua conexão.", 0);
  }

  if (!resposta.ok) {
    let detalhe = "";
    try {
      const corpo = await resposta.json();
      detalhe = typeof corpo.detail === "string" ? corpo.detail : "";
    } catch {
      // resposta sem corpo JSON: cai na mensagem genérica abaixo
    }
    const generica =
      resposta.status >= 500
        ? "O servidor está indisponível ou ainda está iniciando. Tente de novo em instantes."
        : `A requisição falhou (código ${resposta.status}).`;
    throw new ErroApi(detalhe || generica, resposta.status);
  }
  return (await resposta.json()) as T;
}

export const ROTULOS_STATUS: Record<string, string> = {
  respondida: "Respondida",
  sem_informacao: "Sem informação no relatório",
  recusada_fora_escopo: "Fora do escopo",
  recusada_conselho_medico: "Conselho médico recusado",
  bloqueada: "Bloqueada",
  saudacao: "Saudação",
  retida_pelo_auditor: "Retida pelo Auditor",
};

export const ROTULOS_INTENCAO: Record<string, string> = {
  relatorio: "Pergunta sobre o relatório",
  conselho_medico: "Pedido de conselho médico",
  fora_escopo: "Assunto fora do relatório",
  saudacao: "Saudação",
  injecao: "Tentativa de injeção",
  indefinida: "Resumo automático",
};

export const ROTULOS_GERACAO: Record<string, string> = {
  extrativo: "Extrativa (sem LLM)",
  mensagem_fixa: "Mensagem fixa",
};

export const ROTULOS_CHECAGEM: Record<string, string> = {
  fundamentacao: "Fundamentação no relatório",
  numeros: "Números conferem",
  citacoes: "Fontes citadas",
  seguranca: "Sem diagnóstico ou prescrição",
  niveis: "Níveis conferem",
  tamanho: "Tamanho adequado",
  legibilidade: "Facilidade de leitura",
};

export function formatarData(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export function formatarPercentual(valor: number, casas = 1): string {
  return `${(valor * 100).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas })}%`;
}
