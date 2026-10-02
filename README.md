# Vigie

<!-- adam-badges:start -->
[![commits](https://img.shields.io/github/commit-activity/t/Adam-Blf/vigie?color=001329&label=commits&style=flat-square)](https://github.com/Adam-Blf/vigie/commits)
[![visites](https://hits.sh/github.com/Adam-Blf/vigie.svg?style=flat-square&label=visites&color=001329)](https://hits.sh/github.com/Adam-Blf/vigie/)
[![last commit](https://img.shields.io/github/last-commit/Adam-Blf/vigie?color=D4A437&style=flat-square&label=dernier%20push)](https://github.com/Adam-Blf/vigie/commits)
[![top language](https://img.shields.io/github/languages/top/Adam-Blf/vigie?style=flat-square)](https://github.com/Adam-Blf/vigie)
[![license](https://img.shields.io/github/license/Adam-Blf/vigie?style=flat-square&color=D4A437)](LICENSE)
[![ci](https://img.shields.io/github/actions/workflow/status/Adam-Blf/vigie/ci.yml?branch=main&style=flat-square&label=ci)](https://github.com/Adam-Blf/vigie/actions/workflows/ci.yml)
[![version](https://img.shields.io/badge/version-0.1.0-001329?style=flat-square)](CHANGELOG.md)
[![release](https://img.shields.io/github/v/release/Adam-Blf/vigie?style=flat-square&color=001329&label=release)](https://github.com/Adam-Blf/vigie/releases)
[![python](https://img.shields.io/badge/python-3.12-D4A437?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![llm](https://img.shields.io/badge/LLM-Ministral%203%203B%20local-001329?style=flat-square)](docs/adr)
[![k3s](https://img.shields.io/badge/k3s-canary%20Argo%20Rollouts-001329?style=flat-square&logo=kubernetes&logoColor=white)](deploy/k8s)
<!-- adam-badges:end -->

Version 0.1.0 - en construction, suivi jalon par jalon dans [docs/progress.md](docs/progress.md)

Copilote de conformité pour les banques. Vigie répond aux questions sur DORA, l'AI Act, le
RGPD et le règlement anti-blanchiment en citant l'article exact, dit quand il ne trouve
rien dans les textes, et bloque les tentatives de manipulation. Une nouvelle version ne
part en production que si elle passe l'évaluation.

Projet réalisé dans le cadre du cours MLOps, M2 Data Engineering et IA, EFREI Paris.
Projet pédagogique, non affilié officiellement à l'EFREI.

## Architecture

```mermaid
flowchart LR
    user["Utilisateur"]
    web["Interface PWA"]
    api["API FastAPI"]
    guardIn{"Garde-fou d'entrée"}
    blocked["Réponse bloquée"]
    search["Recherche hybride, dense et BM25"]
    qdrant[("Qdrant")]
    llm["Ministral 3 3B via Ollama"]
    guardOut{"Garde-fou de sortie"}
    answer["Réponse citée"]
    audit[("Usage SQLite et journal d'audit")]
    eurlex["EUR-Lex via Cellar"]
    ingest["Ingestion et découpage par article"]

    user --> web
    web -->|"jeton Bearer"| api
    api --> guardIn
    guardIn -->|"injection détectée"| blocked
    guardIn -->|"question saine"| search
    search --> qdrant
    qdrant --> search
    search --> llm
    llm --> guardOut
    guardOut -->|"citation inventée retirée"| answer
    api --> audit
    eurlex --> ingest
    ingest --> qdrant

    classDef input fill:#2563eb,stroke:#1e3a8a,color:#ffffff
    classDef process fill:#0f766e,stroke:#134e4a,color:#ffffff
    classDef store fill:#f59e0b,stroke:#92400e,color:#111111
    classDef ok fill:#16a34a,stroke:#14532d,color:#ffffff
    classDef error fill:#dc2626,stroke:#7f1d1d,color:#ffffff

    class user,web,eurlex input
    class api,guardIn,search,llm,guardOut,ingest process
    class qdrant,audit store
    class answer ok
    class blocked error
```

Chaque bloc correspond à un module de `src/vigie/`, avec une seule responsabilité par
module. Le détail des composants, du budget mémoire et du chemin de livraison est dans
`docs/architecture.md`.

## Démarrage local

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[dev]"
python tasks.py check
```

Le lancement complet en une commande (`docker compose up`) arrive avec le jalon J7.

## Configuration

Toutes les variables d'environnement sont décrites et commentées dans `.env.example`. Elles
portent le préfixe `VIGIE_` et sont lues par `src/vigie/config.py`.

## Contribuer

Une branche par jalon, une pull request par branche, fusion par commit de merge une fois
la CI verte. Chaque commit crédite le binôme (auteur ou co-auteur).

## Auteurs

Adam Beloucif et Emilien Morice.
