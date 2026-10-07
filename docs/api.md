# API

L'API sert les réponses citées de Vigie derrière un jeton. Son contrat est publié dans
[`openapi.json`](openapi.json), généré depuis le code par `python -m vigie.api.contract`
et vérifié par un test : un champ renommé casse la construction avant de casser
l'interface.

## Lancer en local

```sh
# fichiers du classifieur des garde-fous, une seule fois (extra guard-model)
python -m vigie.guard.prepare
# un jeton, affiché une seule fois
python -m vigie.api.tokens create alice
# l'API, sur 127.0.0.1:8710
VIGIE_LLM_PROVIDER=ollama python -m vigie.api
```

Pour mesurer sans index Qdrant, `VIGIE_RETRIEVER=static` et
`VIGIE_STATIC_PASSAGES_PATH=tests/fixtures/dora_art28_passages.json` ; pour une démo sans
modèle, `VIGIE_LLM_PROVIDER=fake`. Le fournisseur se choisit par la configuration ou le
bundle, jamais par une requête.

## Routes

| Route | Jeton | Rôle |
|---|---|---|
| `POST /v1/ask` | `user` | question (1 à 2 000 caractères), réponse JSON complète |
| `POST /v1/ask/stream` | `user` | même chose en SSE : événements `delta`, puis `answer` ou `error` |
| `GET /v1/usage/me` | `user` | requêtes, blocages, refus, jetons du modèle, coût estimé, quota du jour |
| `GET /v1/admin/usage` | `admin` | la même chose pour chaque utilisateur |
| `GET /v1/admin/drift` | `admin` | dérive des questions récentes face à la référence (J9), calculée sur les seuls embeddings |
| `GET /healthz` | aucun | le processus répond |
| `GET /readyz` | aucun | le retriever et le LLM sont joignables, sinon 503 |
| `GET /metrics` | aucun | Prometheus (dont les jauges `vigie_drift_*`), absent du contrat ; Traefik ne route que `/v1` vers l'API |

Chaque réponse porte `trace_id`, `app_version`, `bundle_version`, `prompt_version` et
`model`, en corps et en en-têtes `X-*`, ce qui rend le canary visible depuis l'interface.
Toute réponse produite par le modèle porte en plus `X-AI-Generated: true`, marquage lisible
par machine de l'article 50.2 de l'AI Act ; une question bloquée, qui reçoit un texte fixe,
ne le porte pas ([`compliance/ai-act.md`](compliance/ai-act.md)).
Le flux SSE envoie le texte brut du modèle ; l'événement final `answer` contient la
réponse vérifiée (citations inventées retirées, données personnelles masquées) que
l'interface affiche à la place.

## Erreurs

Toujours `{"error": "<code>", "trace_id": "..."}`, jamais de trace d'exécution.

| Statut | Codes | Cas |
|---|---|---|
| 400 | `bad_request` | corps illisible (pas de l'UTF-8) |
| 401 | `unauthorized` | jeton absent, inconnu, expiré ou révoqué, même réponse dans tous les cas |
| 403 | `forbidden` | jeton `user` sur `/v1/admin/*` |
| 413 | `payload_too_large` | corps au-delà de 16 Ko |
| 422 | `invalid_request` | question vide, trop longue ou champ inconnu, avec `detail` sans écho du texte |
| 429 | `rate_limited`, `quota_exceeded` | limite par minute ou quota quotidien du jeton, avec `Retry-After` |
| 500 | `internal_error` | panne, y compris la panne injectée du canary |
| 503 | `maintenance`, `llm_busy`, `llm_overloaded`, `llm_unavailable` | avec `Retry-After` |
| 503 | `drift_unavailable` | `/v1/admin/drift` sans référence de dérive construite (`vigie-drift build-reference`) |
| 504 | `llm_timeout` | le modèle n'a pas répondu à temps |

## Jetons

`vig_` suivi de 32 octets aléatoires, stocké haché en SHA-256, valable 30 jours, portée
`user` ou `admin`, comparé par `hmac.compare_digest`.

```sh
python -m vigie.api.tokens create <utilisateur> [--scope admin]
python -m vigie.api.tokens list
python -m vigie.api.tokens revoke <id>
python -m vigie.api.tokens rotate-admin <utilisateur>
```

## Usage, audit et journaux

- **Usage** : une ligne par requête traitée dans SQLite en mode WAL (utilisateur, jeton,
  horodatage, statut, latence, jetons, coût, bloqué, refusé), sans texte de question.
  Les lignes de plus de 12 mois (`VIGIE_USAGE_RETENTION_DAYS`, 365 par défaut) sont
  effacées à la première écriture de chaque jour, comme l'empreinte d'un jeton révoqué ou
  expiré depuis plus longtemps.
- **Journal d'audit** : `data/audit/<pod>/<jour>.jsonl`, question et réponse avec les
  données personnelles évidentes masquées, citations, décision des garde-fous, versions
  du modèle, du prompt et du bundle. Ni IP ni User-Agent. Chaque ligne porte le hash de
  la précédente ; `python -m vigie.api.audit_cli verify` signale une ligne modifiée ou
  retirée, `purge` supprime les jours au-delà de 30 jours (l'API le fait seule au premier
  écrit de chaque jour).
- **Journaux applicatifs** : un filtre retire en-tête `Authorization`, jetons et champs
  `question` avant tout gestionnaire.

## Protections

Corps limité à 16 Ko, question à 2 000 caractères, limite par minute et quota quotidien
par jeton, normalisation de la question puis chaîne de garde-fous
([`guardrails-benchmark.md`](guardrails-benchmark.md)), créneaux de génération bornés
(503 avec `Retry-After` au-delà), en-têtes de sécurité, CORS limité à l'interface,
documentation interactive désactivée, coupe-circuit `VIGIE_MAINTENANCE=true`.
