# Architecture de Vigie

Vigie répond aux questions d'une équipe conformité sur DORA, l'AI Act, le RGPD et le
règlement anti-blanchiment, en citant l'article exact. Ce document décrit le chemin d'une
question, le chemin d'une nouvelle version jusqu'à la production, les composants, le rôle
de chaque module Python et le budget mémoire qui arbitre l'ensemble.

Les choix d'hébergement et de modèle sont justifiés dans les ADR 0001 à 0003. Les risques
et leur traitement sont dans `docs/risk-map.md` et `docs/threat-model.md`.

## Chemin d'une requête

```mermaid
sequenceDiagram
    autonumber
    participant UI as Interface PWA
    participant API as API FastAPI
    participant GI as Garde-fou d'entrée
    participant R as Recherche hybride
    participant Q as Qdrant
    participant L as Ollama, Ministral 3 3B
    participant GO as Garde-fou de sortie
    participant A as Journal d'audit
    UI->>API: POST /v1/ask, jeton Bearer
    API->>API: vérifie le jeton, compte l'usage, limite de débit
    API->>GI: question normalisée
    GI-->>API: bloquée ou acceptée
    alt question bloquée
        API-->>UI: blocked, block_reason, trace_id
    else question acceptée
        API->>R: question
        R->>Q: requête dense et BM25
        Q-->>R: passages fusionnés par RRF
        R-->>API: top_k passages
        API->>L: prompt avec passages délimités
        L-->>API: texte en streaming
        API->>GO: réponse et citations
        GO-->>API: citations vérifiées, fuites retirées
        API-->>UI: réponse, citations, version, modèle, durée
    end
    API->>A: trace_id, sources, décision
```

1. L'interface envoie la question avec un jeton Bearer.
2. L'API vérifie le jeton, compte l'usage et applique la limite de débit.
3. Le garde-fou d'entrée bloque l'injection, le jailbreak et la fuite de prompt.
4. La recherche hybride combine embeddings denses multilingues et BM25, fusionnés par RRF
   dans Qdrant.
5. Le LLM répond uniquement à partir des passages, avec des citations de la forme
   `[DORA art. 28 §1]`.
6. Le garde-fou de sortie retire les citations inventées et les fuites de données.
7. L'API renvoie la réponse, les sources et un identifiant de trace, puis écrit le
   journal d'audit.

## Chemin de livraison

Une nouvelle version n'atteint la production que si elle passe l'évaluation, puis le
canary. Le cluster tire lui-même les mises à jour : aucun accès au cluster n'est stocké
dans GitHub.

```mermaid
flowchart LR
    DEV[Branche et commit] --> CI[CI GitHub Actions]
    CI -->|ruff, mypy, pytest, gitleaks| GATE{Barrières vertes}
    GATE -->|non| STOP[Fusion refusée]
    GATE -->|oui| EVAL[Évaluation et red teaming]
    EVAL -->|scores au seuil| MLF[MLflow, version vigie-rag]
    EVAL -->|sous le seuil| STOP
    GATE -->|oui| BUILD[Images arm64 et amd64, SBOM, Trivy, cosign]
    BUILD --> GHCR[(GHCR)]
    MLF -->|alias champion et challenger| CM[ConfigMap vigie-bundle]
    GHCR --> FLUX[Flux dans k3s]
    CM --> FLUX
    FLUX --> RO[Argo Rollouts, canary]
    RO --> AN{Analyse Prometheus}
    AN -->|saine| PROMO[Promotion, alias champion déplacé]
    AN -->|dégradée| ABORT[Retour arrière automatique]
```

## Composants

| Composant | Rôle | Technologie | Exposition |
|---|---|---|---|
| Interface | chat, panneau de citations, réglages, usage | PWA Vite et TypeScript, servie par nginx | publique, derrière TLS |
| API | authentification, usage, garde-fous, orchestration RAG, audit, métriques | FastAPI, uvicorn | publique sous `/v1`, derrière TLS |
| Garde-fous | filtrage en entrée et en sortie | regex, classifieur ONNX int8, retenu par le benchmark J4 | interne |
| Recherche | embeddings denses et creux, fusion RRF | fastembed, Qdrant | interne |
| Base vectorielle | stockage des passages et des vecteurs | Qdrant, clé d'API | interne |
| LLM | rédaction de la réponse citée | Ollama, `ministral-3:3b-instruct-2512-q4_K_M` | interne |
| Suivi des modèles | versions, scores, alias | MLflow, backend SQLite | interne, `port-forward` seulement |
| Métriques | taux d'erreur, latence, taux de blocage par version | Prometheus | interne |
| Orchestration | pods, scaling, canary | k3s, Argo Rollouts, Flux, Traefik | Traefik seul exposé |
| Infrastructure | VM, réseau, sauvegardes, budget | Terraform, Oracle Cloud Always Free | SSH par clé, IP d'administration |

Ports locaux réservés à Vigie, tous liés à `127.0.0.1` : API 8710, interface 4710,
Qdrant 6733 et 6734, MLflow 5710, Prometheus 9710.

## Carte des modules

Chaque sous-paquet a une seule responsabilité. Un module qui en prend une seconde est
découpé.

| Module | Responsabilité unique |
|---|---|
| `vigie.config` | lire toute la configuration depuis l'environnement (`VIGIE_*`), avec un seul jeu de valeurs par défaut |
| `vigie.corpus` | télécharger les textes depuis Cellar, vérifier leurs empreintes, parser le XHTML et découper par article |
| `vigie.retrieval` | calculer les embeddings, alimenter la collection Qdrant et exécuter la recherche hybride |
| `vigie.llm` | exposer une interface commune aux fournisseurs de LLM (Ollama, faux LLM, Mistral pour comparaison) |
| `vigie.rag` | construire le prompt, enchaîner recherche et génération, valider les citations |
| `vigie.guard` | appliquer en production les garde-fous d'entrée et de sortie retenus par le benchmark |
| `vigie.api` | servir HTTP : application, authentification, usage, audit, schémas, métriques |
| `vigie.drift` | détecter la dérive des questions entrantes par rapport au jeu de référence |
| `vigie.evaluation` | évaluer une version sur le jeu de référence et journaliser les scores dans MLflow |
| `guardbench` | comparer plusieurs garde-fous sur un même jeu étiqueté, hors du chemin de production |

`guardbench` est volontairement séparé de `vigie` : le benchmark peut dépendre d'outils
lourds (torch, modèles de classification) qui ne doivent jamais entrer dans l'image de
production de l'API.

## Budget mémoire sur 12 Go

La VM Always Free offre 12 Go. 1,5 Go reste à l'OS. La somme des `requests` ne dépasse
pas 8,5 Go, celle des `limits` pas 10,5 Go. Les valeurs ci-dessous sont des estimations ;
elles seront mesurées à la conteneurisation (J7) puis figées ici.

| Composant | Mémoire estimée |
|---|---|
| k3s, Traefik, CoreDNS, metrics-server | 1,2 Go |
| Ollama avec Ministral 3B Q4 (une instance partagée) | 3,0 Go |
| Qdrant | 0,4 Go |
| MLflow (1 worker) | 0,4 Go |
| Prometheus (rétention 24 h) | 0,4 Go |
| Argo Rollouts, Flux | 0,2 Go |
| web | 0,05 Go |
| API (par pod, sans torch) | 0,7 Go, 3 pods au plus (HPA 2 plus 1 canary) |
| **Total au pic** | **7,75 Go**, soit 0,75 Go de marge sous le plafond de 8,5 Go |

Deux conséquences structurent le code. L'image de l'API ne contient pas torch : le
garde-fou d'entrée repose sur des règles et un classifieur ONNX int8. Et la ligne
d'Ollama est la plus fragile, puisque les poids Q4_K_M pèsent déjà 2,95 Go avant le cache
KV (ADR 0003).

## Projets dont Vigie s'inspire

Les trois dépôts ont été vérifiés le 2 octobre 2026 avec `gh api`. Aucun code n'en est
copié : `eu-ai-act-rag` n'affiche pas de licence et `k3s-aws-terraform-cluster` est sous
GPL 3.0, seules les idées sont reprises.

| Projet | Ce qu'il fait | Ce que Vigie reprend | Ce que Vigie ajoute |
|---|---|---|---|
| [RostislavDublin/eu-ai-act-rag](https://github.com/RostislavDublin/eu-ai-act-rag) | assistant RAG sur l'AI Act, application Streamlit avec recherche hybride, accès contrôlé et métriques d'évaluation | recherche hybride sur un règlement européen, évaluation intégrée | quatre règlements, citation à l'article et au paragraphe validée contre le corpus, garde-fous benchmarkés, déploiement canary piloté par les scores |
| [HamzaG737/legal-code-rag](https://github.com/HamzaG737/legal-code-rag) | évaluation de RAG avancé sur les codes juridiques français | méthode d'évaluation d'un RAG juridique en français | jeu de référence scellé, barrière d'évaluation en CI, suivi des versions dans MLflow |
| [garutilorenzo/k3s-aws-terraform-cluster](https://github.com/garutilorenzo/k3s-aws-terraform-cluster) | cluster k3s hautement disponible sur AWS, décrit en Terraform | k3s provisionné par Terraform | version mono-nœud Always Free à coût nul, CD tirée par Flux, canary Argo Rollouts, durcissement du namespace |

En résumé, ces projets traitent chacun une partie du problème : la recherche juridique,
l'évaluation ou l'infrastructure. Vigie les assemble dans une chaîne MLOps complète, où la
sécurité (garde-fous, red teaming en CI) et la preuve (évaluation, canary, journal
d'audit) conditionnent chaque mise en production.
