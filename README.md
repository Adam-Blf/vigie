# Vigie

<!-- adam-badges:start -->
[![ci](https://github.com/Adam-Blf/vigie/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Adam-Blf/vigie/actions/workflows/ci.yml)
[![version](https://img.shields.io/badge/version-0.1.0-001329?style=flat-square)](CHANGELOG.md)
[![visites](https://hits.sh/github.com/Adam-Blf/vigie.svg?style=flat-square&label=visites&color=001329)](https://hits.sh/github.com/Adam-Blf/vigie/)
[![licence](https://img.shields.io/badge/licence-MIT-D4A437?style=flat-square)](LICENSE)
[![python](https://img.shields.io/badge/python-3.12-D4A437?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![fastapi](https://img.shields.io/badge/FastAPI-API-001329?style=flat-square&logo=fastapi&logoColor=white)](src/vigie/api)
[![qdrant](https://img.shields.io/badge/Qdrant-recherche%20hybride-001329?style=flat-square)](src/vigie/retrieval)
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
    user([Utilisateur]):::input --> web[Interface PWA]:::input
    web -->|jeton Bearer| api[API FastAPI]:::process
    api --> guardIn{Garde-fou d'entrée}:::process
    guardIn -->|injection détectée| blocked[Réponse bloquée]:::error
    guardIn -->|question saine| search[Recherche hybride dense + BM25]:::process
    search <--> qdrant[(Qdrant)]:::store
    search --> llm[Ministral 3 3B via Ollama]:::process
    llm --> guardOut{Garde-fou de sortie}:::process
    guardOut -->|citation inventée retirée| answer[Réponse citée]:::ok
    api --> audit[(Usage SQLite et journal d'audit)]:::store
    eurlex[EUR-Lex via Cellar]:::input --> ingest[Ingestion et découpage par article]:::process
    ingest --> qdrant

    classDef input fill:#2563eb,stroke:#1e3a8a,color:#fff
    classDef process fill:#0f766e,stroke:#134e4a,color:#fff
    classDef store fill:#f59e0b,stroke:#92400e,color:#111
    classDef ok fill:#16a34a,stroke:#14532d,color:#fff
    classDef error fill:#dc2626,stroke:#7f1d1d,color:#fff
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
