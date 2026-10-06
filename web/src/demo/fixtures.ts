// Seven frozen answers for demo mode (?demo=1), the e2e tests, the README captures and
// the GIF. They cover every mascot outcome. Excerpts are short quotations of the French
// versions on EUR-Lex; the demo banner reminds readers that only the Official Journal
// is authentic.

import type { AskResponse, Citation, UsageResponse } from "../api/types.ts";

const CELEX = {
  dora: "32022R2554",
  aiAct: "32024R1689",
  gdpr: "32016R0679",
} as const;

function eurlex(celex: string): string {
  return `https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:${celex}`;
}

function citation(
  regulation: string,
  celex: string,
  article: string,
  paragraph: string | null,
  excerpt: string,
): Citation {
  const label = paragraph
    ? `[${regulation} art. ${article} §${paragraph}]`
    : `[${regulation} art. ${article}]`;
  return { label, regulation, article, paragraph, excerpt, url: eurlex(celex) };
}

const BASE = {
  blocked: false,
  block_reason: null,
  refused: false,
  app_version: "0.1.0",
  bundle_version: "demo",
  model: "ministral-3-3b",
  corpus_date: "2026-10-02",
} as const;

export interface DemoFixture {
  id: string;
  keywords: readonly string[];
  response: AskResponse;
}

const DORA_28 = citation(
  "DORA",
  CELEX.dora,
  "28",
  "3",
  "Dans le cadre de leur cadre de gestion du risque lié aux TIC, les entités financières tiennent et mettent à jour, au niveau de l'entité ainsi qu'aux niveaux sous-consolidé et consolidé, un registre d'informations en rapport avec tous les accords contractuels portant sur l'utilisation de services TIC fournis par des prestataires tiers de services TIC.",
);

const AI_ACT_50 = citation(
  "AI Act",
  CELEX.aiAct,
  "50",
  "1",
  "Les fournisseurs veillent à ce que les systèmes d'IA destinés à interagir directement avec des personnes physiques soient conçus et développés de manière que les personnes physiques concernées soient informées qu'elles interagissent avec un système d'IA.",
);

const GDPR_33 = citation(
  "RGPD",
  CELEX.gdpr,
  "33",
  "1",
  "En cas de violation de données à caractère personnel, le responsable du traitement en notifie la violation en question à l'autorité de contrôle compétente conformément à l'article 55, dans les meilleurs délais et, si possible, 72 heures au plus tard après en avoir pris connaissance.",
);

const DORA_19 = citation(
  "DORA",
  CELEX.dora,
  "19",
  "1",
  "Les entités financières notifient les incidents majeurs liés aux TIC à l'autorité compétente concernée visée à l'article 46.",
);

const AI_ACT_4 = citation(
  "AI Act",
  CELEX.aiAct,
  "4",
  null,
  "Les fournisseurs et les déployeurs de systèmes d'IA prennent des mesures pour garantir, dans toute la mesure du possible, un niveau suffisant de maîtrise de l'IA pour leur personnel.",
);

export const DEMO_FIXTURES: readonly DemoFixture[] = [
  {
    id: "dora-incident",
    keywords: ["incident", "déclarer", "report"],
    response: {
      ...BASE,
      answer: `Les incidents majeurs liés aux TIC sont notifiés à l'autorité compétente désignée par l'article 46 de DORA ${DORA_19.label}.`,
      citations: [DORA_19],
      trace_id: "demo-0004",
      latency_ms: 1710,
    },
  },
  {
    id: "dora-register",
    keywords: ["contrat", "prestataire", "tic", "third-party", "contract"],
    response: {
      ...BASE,
      answer: `DORA impose de tenir un registre d'informations sur tous les accords contractuels portant sur des services TIC fournis par des prestataires tiers, au niveau de l'entité comme aux niveaux sous-consolidé et consolidé ${DORA_28.label}.`,
      citations: [DORA_28],
      trace_id: "demo-0001",
      latency_ms: 1840,
    },
  },
  {
    id: "ai-act-transparency",
    keywords: ["transparence", "chatbot", "transparency", "interagi"],
    response: {
      ...BASE,
      answer: `Un système d'IA qui interagit directement avec des personnes doit être conçu pour qu'elles sachent qu'elles parlent à une IA, sauf si c'est évident dans le contexte ${AI_ACT_50.label}.`,
      citations: [AI_ACT_50],
      trace_id: "demo-0002",
      latency_ms: 1620,
    },
  },
  {
    id: "gdpr-breach",
    keywords: ["violation", "breach", "délai", "notifier"],
    response: {
      ...BASE,
      answer: `Le responsable du traitement notifie la violation à l'autorité de contrôle compétente dans les meilleurs délais et, si possible, dans les 72 heures après en avoir pris connaissance ${GDPR_33.label}.`,
      citations: [GDPR_33],
      trace_id: "demo-0003",
      latency_ms: 1490,
    },
  },
  {
    id: "out-of-scope",
    keywords: ["recette", "météo", "football", "recipe", "weather"],
    response: {
      ...BASE,
      answer:
        "Aucun article de DORA, de l'AI Act, du RGPD ou de l'AMLR ne répond à cette question. Reformulez-la si elle porte sur l'un de ces textes.",
      citations: [],
      refused: true,
      trace_id: "demo-0005",
      latency_ms: 620,
    },
  },
  {
    id: "injection",
    keywords: ["ignore", "instructions", "oublie", "prompt"],
    response: {
      ...BASE,
      answer: "",
      citations: [],
      blocked: true,
      block_reason: "injection",
      trace_id: "demo-0006",
      latency_ms: 85,
    },
  },
  {
    id: "ai-literacy",
    keywords: ["maîtrise", "formation", "literacy", "personnel"],
    response: {
      ...BASE,
      answer: `Fournisseurs et déployeurs doivent assurer à leur personnel un niveau suffisant de maîtrise de l'IA ${AI_ACT_4.label}.`,
      citations: [AI_ACT_4],
      citations_removed: 1,
      trace_id: "demo-0007",
      latency_ms: 1930,
    },
  },
];

export const DEMO_USAGE: UsageResponse = {
  requests_today: 7,
  daily_quota: 50,
  requests: 42,
  blocked: 3,
  refused: 5,
};

// Word-prefix match, so "tic" never fires inside "article". Anything unmatched gets the
// out-of-scope refusal: in demo mode an unknown question still deserves an honest answer.
export function findDemoFixture(question: string): DemoFixture {
  const words = question.toLowerCase().split(/[^\p{L}\p{N}]+/u);
  const match = DEMO_FIXTURES.find((fixture) =>
    fixture.keywords.some((keyword) => words.some((word) => word.startsWith(keyword))),
  );
  const fallback = DEMO_FIXTURES.find((fixture) => fixture.id === "out-of-scope");
  if (match) return match;
  if (!fallback) throw new Error("demo fixtures lost their out-of-scope answer");
  return fallback;
}
