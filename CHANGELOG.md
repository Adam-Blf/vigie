# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions en
[SemVer](https://semver.org/lang/fr/). Chaque version publiée a sa release GitHub, dont
les notes reprennent la section correspondante.

## [Unreleased]

## [0.6.0] - 2026-10-06

### Added

- Détection de drift du jalon J9 (`src/vigie/drift/`) : fenêtre glissante bornée qui ne
  garde que des vecteurs, trois indicateurs (distance entre centroïdes, part de questions
  hors périmètre, test de Kolmogorov-Smirnov écrit en numpy), jauges Prometheus et journal
  des transitions d'alerte.
- Commande `vigie-drift build-reference` et tâche `python tasks.py drift-reference` qui
  construisent `data/drift/reference.npy` et `anchors.npy` depuis le jeu de référence et
  le corpus, avec repli sur la fixture de test.
- Tâche `python tasks.py test-integration` pour les tests marqués `integration`, exclus par
  défaut, qui chargent le vrai modèle MiniLM.
- Documentation `docs/drift.md` et preuves du jalon dans `docs/proofs/J9/` (rapport avant
  et après un lot hors sujet, marge du test KS).
- Réglages `VIGIE_DRIFT_*`, décrits dans `.env.example`.

## [0.5.0] - 2026-10-06

### Added

- Banc d'essai des garde-fous du jalon J4 (`src/guardbench`, commande `guardbench`) : jeu
  maison bilingue de 174 exemples en neuf catégories, découpage `dev` et `test` figé par
  paire, adaptateurs regex de référence, DeBERTa v3 ProtectAI, GLiGuard 300M, Presidio,
  Llama Guard 3 1B via Ollama et Lakera Guard, mesure chronométrée avec échauffement,
  rapports CSV, Markdown et graphique qualité contre latence, suivi MLflow en SQLite.
- Rapport `docs/guardrails-benchmark.md` et preuves du jalon dans `docs/proofs/J4/bench/`
  (jeu maison `test` et contrôle `deepset/prompt-injections`).
- Réglages `VIGIE_BENCH_*`, `VIGIE_LAKERA_URL` et `VIGIE_MLFLOW_TRACKING_URI`, décrits dans
  `.env.example`.
- Licence propriétaire, tous droits réservés, dépôt public en consultation seule.

### Changed

- Bandeau de badges du README réduit à sept badges cohérents et centrés.

## [0.4.0] - 2026-10-02

### Added

- Jeu de référence du jalon J8 (`data/golden/questions.jsonl`) : 80 questions sur DORA,
  l'AI Act, le RGPD et l'AMLR, dont 60 dans le périmètre, 10 hors périmètre et 10 pièges,
  56 en français et 24 en anglais. Chaque question porte ses articles attendus et une
  citation de référence vérifiée mot pour mot dans le texte Cellar par le second auteur.
- Répartition stratifiée en 54 questions `dev` et 26 questions `test`, la partie `test`
  scellée par son empreinte SHA-256 dans `data/golden/test.sha256` ; `data/golden/README.md`
  donne le tableau par catégorie et les lignes utilisées par chaque indicateur.
- Commande `vigie-eval` : `validate-golden` vérifie chaque question contre le corpus
  (articles connus, citation présente dans le texte, statut vérifié, sceau intact) et
  sort en erreur au moindre écart, `seal-golden` réécrit le sceau et exige `--force` si
  la partie `test` a changé.
- Indicateurs déterministes dans `src/vigie/evaluation/metrics.py` : rappel@k, MRR, taux de
  refus correct, validité brute des citations, nombre de citations inventées restées dans
  la réponse finale, précision et couverture des citations, intervalle de confiance par
  bootstrap.
- Seuils d'évaluation écrits avant toute mesure dans `eval/thresholds.yaml` (rappel@5 au
  moins 0,80, MRR au moins 0,60, aucune citation inventée dans la réponse finale, refus
  correct au moins 0,90, recul maximal de 2 points face au champion).
- Réglages `VIGIE_GOLDEN_PATH` et `VIGIE_GOLDEN_SEAL_PATH`, décrits dans `.env.example`.
- Preuves du jalon J8 dans `docs/proofs/J8/` : validation verte sur les 366 articles du
  corpus, et deux validations vues rouges (questions encore en brouillon, copie dégradée).

### Changed

- Le taux de refus correct se mesure sur les 10 questions hors périmètre, `dev` et `test`
  réunies, et non sur les 3 de la partie `test`, pour éviter des pas de 33 points.
- La table des numéros CELEX de l'évaluation se déduit du registre du corpus au lieu d'en
  garder une copie.

### Fixed

- `vigie-eval validate-golden` lit aussi les fichiers `<CELEX>.fra.xhtml` du cache de
  `vigie-ingest`, qu'il ignorait faute de reconnaître leur nom.

## [0.3.0] - 2026-10-02

### Added

- Couche LLM du jalon J3 : interface de génération en flux commune à trois fournisseurs,
  Ollama local par défaut (Ministral 3 3B), Mistral payant désactivé sans clé, et faux LLM
  déterministe pour les tests et les tirs de charge (`src/vigie/llm/`).
- Chaîne RAG question, passages, prompt, génération et contrôle des citations
  (`src/vigie/rag/`) : le prompt système français (version v2) délimite chaque passage et
  impose de recopier son étiquette, et toute réponse qui ne s'appuie sur aucun passage
  devient le refus explicite « Je ne trouve pas de réponse dans les textes indexés. »
- Validateur de citations qui reconnaît les variantes d'écriture d'un renvoi (virgule après
  le code, article en tête, `article`, `para.`, `§`, lettre de point, alias AI Act, GDPR,
  LCB-FT) et retire de la réponse finale toute citation qui ne correspond à aucun passage
  fourni, en la listant dans `removed_citations`.
- Commande `python -m vigie.rag.cli --passages <fichier.json> "question"` qui affiche la
  réponse en flux et écrit la réponse validée en JSON, avec les temps du premier jeton et de
  la réponse complète.
- Réglages `VIGIE_LLM_*`, `VIGIE_MISTRAL_URL`, `VIGIE_MISTRAL_MODEL`, `VIGIE_RAG_MIN_SCORE`,
  `VIGIE_RAG_REQUIRE_CITATION` et `FAKE_LLM_HALLUCINATE`, décrits dans `.env.example`.
- Preuves du jalon J3 dans `docs/proofs/J3/` : trois réponses réelles de Ministral 3B sur
  DORA art. 28 (premier jeton à 6,1 s modèle chaud, réponse complète en 49 s sur le poste
  de développement) et une citation inventée par le faux LLM retirée de la réponse.

### Changed

- Une réponse qui contient la phrase de refus à côté d'au moins une citation valide est
  gardée comme réponse partielle, la phrase de refus en moins.
- La version du prompt n'existe plus que dans `vigie.rag.prompt`, le réglage
  `prompt_version` inutilisé est supprimé.

### Fixed

- Les clients HTTP d'Ollama et de Mistral sont fermés après chaque question.

## [0.2.0] - 2026-10-02

### Added

- Corpus réglementaire du jalon J1 : DORA, AI Act, RGPD et AMLR téléchargés en français
  depuis Cellar, en HTTPS uniquement, avec cache local, une requête par seconde au plus et
  reprises avec repli progressif (`src/vigie/corpus/`).
- Découpage du XHTML du Journal officiel par article et par paragraphe, annexes comprises,
  chaque morceau portant son ancre EUR-Lex (`eid`) et son URL de citation ; 511 morceaux sur
  les quatre textes, considérants exclus par défaut.
- Commande `vigie-ingest` (`--only`, `--recitals`, `--update-lock`, `--lock`, `--out`,
  `--from-url`) qui écrit un fichier JSONL par règlement dans `data/corpus/`, documentée
  dans `docs/corpus.md`.
- Verrou `data/corpus.lock` qui fige CELEX, empreinte sha256 et nombre d'articles des
  textes téléchargés le 2026-10-02 : une ingestion s'arrête dès qu'un texte diffère.
- Lecture d'un corpus JSONL déjà publié comme solution de repli quand Cellar ne répond pas.
- Réglages d'ingestion `VIGIE_CORPUS_*`, `VIGIE_CELLAR_*` et `VIGIE_EURLEX_BASE_URL`,
  décrits dans `.env.example`.
- Preuves du jalon J1 dans `docs/proofs/J1/`, dont les deux refus du verrou vus en rouge.

### Changed

- `NOTICE` liste les quatre règlements avec leur CELEX et les conditions de réutilisation
  d'EUR-Lex.

### Fixed

- Le paquet déclare la licence propriétaire sur toutes les branches, plus aucune mention
  MIT héritée.

## [0.1.1] - 2026-10-02

### Added

- Cartographie des risques OWASP LLM 2025 appliquée aux surfaces de Vigie
  (`docs/risk-map.md`) et modèle de menaces STRIDE flux par flux
  (`docs/threat-model.md`).
- Trois décisions d'architecture : hébergement à coût nul, Oracle Cloud Always Free, LLM
  local Ministral 3 3B servi par Ollama (`docs/adr/`).
- Description des chemins de requête et de livraison dans `docs/architecture.md`.
- Guide de contribution du binôme (`CONTRIBUTING.md`) et avis de réutilisation des textes
  EUR-Lex (`NOTICE`).
- Tâche `python tasks.py typo` qui refuse tirets longs, demi-cadratins, médiopoints et
  caractères invisibles dans les fichiers suivis du dépôt.
- Preuves du jalon J0 cadrage dans `docs/proofs/J0-cadrage/`.

### Changed

- Les tests de configuration ne lisent plus le fichier `.env` local, ils passent par une
  sous-classe typée de `Settings`, ce qui rend `mypy tests src` propre.

### Fixed

- Journal de preuve du J0 outillage débarrassé des chemins locaux de la machine de build.

## [0.1.0] - 2026-10-02

### Added

- Squelette du dépôt : paquets `vigie` et `guardbench`, configuration centralisée dans
  `src/vigie/config.py`, lanceur de tâches `tasks.py`.
- Outillage qualité : ruff, mypy strict, pytest avec couverture, pre-commit avec gitleaks.
- Hook de co-auteur du binôme sur chaque commit local.
- CI qualité sur chaque pull request et sur `main`, `main` protégée par un ruleset.
- Suivi de progression dans `docs/progress.md` et preuve du J0 outillage.
- README avec badges, ligne de version et architecture en Mermaid coloré, compatible avec
  le rendu de GitHub.
- Politique de sécurité `SECURITY.md` avant le passage du dépôt en public.
- Synchronisation de la version du README depuis `pyproject.toml`
  (`scripts/sync_version.py`) et notes de release tirées du CHANGELOG
  (`scripts/release_notes.py`).
- Workflow de release sur tag `vX.Y.Z` : contrôle du tag, wheel et sdist joints, images
  publiées sur GHCR dès que les Dockerfiles existent.
