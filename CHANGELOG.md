# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions en
[SemVer](https://semver.org/lang/fr/). Chaque version publiée a sa release GitHub, dont
les notes reprennent la section correspondante.

## [Unreleased]

## [0.17.0] - 2026-10-07

### Added

- Pile Docker du jalon J7 (niveau 0) : `python tasks.py up` construit, démarre et attend
  `qdrant`, le job `ingest` (téléchargement Cellar, découpage, `vigie-index`, référence de
  dérive), `api`, `web` et `mlflow`, puis affiche une seule fois un jeton de
  démonstration ; `python tasks.py down` arrête tout en gardant les volumes. Profil
  `local-llm` avec Ollama (`OLLAMA_NUM_PARALLEL=1`, file de 4) et le téléchargement du
  modèle ; sans lui, le LLM est le faux. Ports liés à `127.0.0.1` seulement.
- `deploy/docker/api.Dockerfile` : multi-étapes, bases épinglées par digest, `uv sync
  --frozen`, sans torch, utilisateur 10001, modèles d'embedding et classifieur ONNX int8
  intégrés au build dans une couche dédiée, puis rechargés sans réseau sous l'utilisateur
  non root (`python -m vigie.deploy.models`), système de fichiers racine en lecture seule.
  L'étape des modèles tourne sur la plateforme du builder (fichiers ONNX identiques pour
  amd64 et arm64) : l'image arm64 ne quantifie plus sous QEMU, elle recharge seulement les
  modèles sous l'architecture cible.
- Job unique `volumes-init` (root avec la seule capacité `CHOWN`, sans réseau) : MLflow et
  Ollama tournent sous l'uid 1000, comme leurs pods de `deploy/k8s`, et plus en root.
- `deploy/docker/web.Dockerfile` : build Vite sur la plateforme du builder, nginx non
  root avec la CSP et les en-têtes de sécurité du brief, `/v1` relayé vers l'API sous la
  même origine, `config.json` jamais mis en cache.
- `GET /v1/admin/drift` (jeton `admin`, 403 pour `user`, 503 sans référence) et jauges
  `vigie_drift_*` dans `/metrics` : l'embedding déjà calculé pour la recherche alimente
  la fenêtre de dérive du J9, sans le texte de la question.
- `uv.lock` versionné ; toutes les dépendances d'exécution ont une roue `aarch64`.

### Changed

- `VIGIE_LLM_TIMEOUT_S` traverse Compose jusqu'au conteneur de l'API (120 s par défaut) : le LLM
  local sur processeur seul demande 900 s dans `.env` (271 s mesurées pour une réponse).
- Le job de red teaming de la CI démarre la pile Compose avec une clé Qdrant aléatoire
  propre au runner, et dispose de 30 minutes pour le premier build.

### Fixed

- `test_cli_without_passages_retrieves_from_qdrant` échouait dès qu'un `.env` écrit par
  `tasks.py up` définissait `VIGIE_QDRANT_URL` : le test l'écarte, la suite ne dépend plus de
  l'état de la pile Docker.

## [0.16.0] - 2026-10-06

### Added

- Interface PWA du jalon J6 (`web/`) : TypeScript strict avec Vite et Preact, écran de
  conversation avec réponses en flux et panneau de citations, écrans réglages, usage,
  mentions légales, confidentialité et statut, dictionnaires français et anglais à clés
  identiques, chouette de repli en SVG et contrat d'animation Rive.
- Service worker en mode invite, coquille hors ligne, aucune réponse de l'API mise en
  cache, politique CSP de production avec Trusted Types, icônes Phosphor et ressources
  servies localement, sans CDN.
- Jetons de design avec barrière de contraste (`python tasks.py contrast`), suite
  Playwright (conversation, PWA, accessibilité axe, origines, captures visuelles) et
  configuration Lighthouse CI.
- Description de chaque écran dans `docs/design/screens.md` et preuves du jalon dans
  `docs/proofs/J6/`.

## [0.15.0] - 2026-10-06

### Added

- Étude de quantization du jalon J12 (`src/vigie/quant/`, commande `vigie-quant`) : export
  ONNX fp32 du modèle d'embedding à révision épinglée, quantization dynamique int8 par
  onnxruntime, contrôle de parité avec PyTorch, puis mesure de la taille, de la latence
  p50 et p95 par requête, du rappel@5 et du MRR sur la partie `dev` du jeu de référence,
  chaque variante journalisée comme un run MLflow.
- Seuil de décision écrit avant la mesure dans `eval/thresholds.yaml` (section
  `quantization`) : int8 retenu si le rappel@5 perd au plus 2 points et si le fichier est
  au moins divisé par 2.
- Étude LLM Ministral 3B Q4_K_M contre Q8_0 par Ollama, sur CPU seul : premier token,
  débit, mémoire et validité des citations sur 10 questions `dev` fixes.
- Documentation `docs/quantization.md` avec tableau et graphique, preuves dans
  `docs/proofs/J12/`, réglages `VIGIE_DENSE_VARIANT`, `VIGIE_DENSE_MODEL_REVISION` et
  `VIGIE_QUANT_*` décrits dans `.env.example`.

### Changed

- Le modèle d'embedding déployé est la version int8 (`dense_variant = "int8"`) : taille
  divisée par 4, rappel@5 sans perte sur la partie `dev`. Ministral 3B reste en Q4_K_M :
  Q8_0 double l'attente du premier token et ajoute 1,5 Go pour une qualité identique.
- `pyyaml` passe dans les dépendances d'exécution, l'extra `quant` gagne torch,
  transformers, onnxscript et matplotlib.

## [0.14.0] - 2026-10-06

### Added

- API sécurisée du jalon J5 (`python -m vigie.api`, 127.0.0.1:8710) : `POST /v1/ask` et
  sa version en flux SSE `POST /v1/ask/stream`, `GET /v1/usage/me`,
  `GET /v1/admin/usage`, `GET /healthz`, `GET /readyz`, `GET /metrics`. Chaque réponse
  porte `trace_id`, versions de l'application, du bundle et du prompt, modèle et latence.
- Jetons `vig_` de 32 octets aléatoires, stockés hachés en SHA-256, valables 30 jours,
  portée `user` ou `admin`, commandes `python -m vigie.api.tokens create`, `list`,
  `revoke` et `rotate-admin` ; 401 identique pour un jeton absent, inconnu, expiré ou
  révoqué, 403 pour un jeton `user` sur `/v1/admin/*`.
- Suivi d'usage dans SQLite en mode WAL, une ligne par requête sans texte de question,
  quota quotidien par jeton et limite par minute, tous deux avec `Retry-After`.
- Journal d'audit AI Act en JSONL par pod, chaîné par hash, sans IP ni User-Agent, données
  personnelles masquées, purge automatique à 30 jours, `python -m vigie.api.audit_cli
  verify` et `purge`.
- Filtre de rédaction des journaux (en-tête `Authorization`, jetons, champs `question`),
  corps limité à 16 Ko, erreurs génériques avec `trace_id`, en-têtes de sécurité, CORS
  restreint, coupe-circuit `VIGIE_MAINTENANCE`, créneaux de génération bornés (503 avec
  `Retry-After`), compteur dédié aux erreurs du LLM, panne injectable par le bundle.
- Bundle de version lu depuis un fichier (`VIGIE_BUNDLE_PATH`), jamais depuis MLflow ;
  le démarrage échoue si sa version de prompt diffère de celle du code.
- Contrat publié dans `docs/openapi.json` (`python -m vigie.api.contract`), vérifié par
  un test ; documentation dans `docs/api.md`, réglages dans `.env.example`.
- Preuves dans `docs/proofs/J5/` : appels `curl` réels avec le faux LLM et avec
  Ministral 3B servi par Ollama, jetons masqués.

## [0.13.0] - 2026-10-06

### Added

- Chaîne CI/CD du jalon J15 : actions tierces épinglées par SHA complet, contrôle des
  workflows par actionlint vérifié par somme de contrôle, crédit du binôme sur chaque commit
  d'une pull request (`scripts/check_coauthors.py`), recherche de secrets par gitleaks,
  audit des dépendances Python et npm, tests de l'interface, porte d'évaluation et porte de
  red teaming qui démarrent dès que leurs prérequis existent.
- Planchers de couverture par module critique (`scripts/coverage_gate.py`, tâche
  `python tasks.py coverage-gate`, appelée par `check`) : 80 % au total, 95 % sur les
  garde-fous, les citations, l'authentification, l'usage et le drift.
- Publication d'images multi-architecture signées sans clé par cosign, avec SBOM et scan
  Trivy (`.github/workflows/build.yml`), et Dependabot pour pip, npm, les actions et Docker.
- Documentation `docs/cicd.md`, preuves du jalon dans `docs/proofs/J15/` et barrières vues
  rouges dans `docs/proofs/gates/`.

### Changed

- Le job `quality` vérifie aussi la version du README.
- Les images ne sont plus publiées par `release.yml` : `build.yml` s'en charge aussi sur
  les tags de version, signées et scannées.

## [0.12.0] - 2026-10-06

### Added

- Chaîne de garde-fous de production du jalon J4 dans `src/vigie/guard/` : normalisation
  de l'entrée (NFKC, caractères invisibles et bidirectionnels retirés, base64,
  encodage pourcentage et entités HTML décodés), regex de référence reprise de
  `src/guardbench`, puis classifieur DeBERTa ProtectAI v2 en ONNX int8 pour les textes
  en anglais, sans torch.
- Chaîne de sortie : seconde vérification des citations contre les passages retrouvés
  et masquage des e-mails, IBAN, cartes (Luhn) et téléphones.
- `python -m vigie.guard.prepare` télécharge l'export ONNX à une révision épinglée, le
  quantifie en int8 par canal (738 Mo vers 244 Mo) et écrit un manifeste d'empreintes ;
  extra `guard-model` pour cette étape de construction.
- `python -m vigie.guard.measure` mesure la chaîne sur le jeu maison contre la nouvelle
  section `guard` de `eval/thresholds.yaml` et sort en erreur si un seuil manque.
- Réglages `VIGIE_GUARD_*` décrits dans `.env.example` ; `onnxruntime` et `tokenizers`
  deviennent des dépendances directes.
- Preuves dans `docs/proofs/J4/guard/` : sur `test`, rappel des injections directes 1,0
  en français et en anglais, aucun faux positif, p95 de 96 ms.

### Changed

- `scripts/sync_version.py` réécrit aussi `__version__` de `src/vigie/__init__.py`, que
  l'API renverra dans chaque réponse.

### Removed

- Réglage `guard_enabled`, jamais lu, remplacé par `VIGIE_GUARD_CLASSIFIER`.

## [0.11.0] - 2026-10-06

### Added

- Manifestes Kubernetes du jalon J13 (`deploy/k8s/`) : base kustomize avec déploiement
  canary Argo Rollouts et analyse Prometheus, pods durcis (Pod Security restricted),
  politiques réseau, Qdrant avec instantanés, Ollama, MLflow, Prometheus et interface web,
  surcouches `dev`, `prod` et `prod-loadtest`.
- Livraison continue en mode tiré avec l'automatisation d'images de Flux (`deploy/k8s/cd/`)
  et versions épinglées des modules dans `deploy/versions.env`.
- Contrôle du budget du nœud unique (`python -m vigie.deploy`) : requêtes, limites et CPU
  des manifestes rendus jugés contre les réglages `VIGIE_K8S_*`, décrits dans
  `.env.example`.
- Tâche `python tasks.py k8s-validate` qui rend chaque couche, la valide avec kubeconform
  puis vérifie le budget.
- Documentation `deploy/k8s/README.md` et preuves du jalon dans `docs/proofs/J13/`
  (validation, budget vu rouge, essais côté serveur, grappe k3d de développement).

## [0.10.0] - 2026-10-06

### Added

- Recherche hybride du jalon J2 (`src/vigie/retrieval/`) : embeddings denses fastembed
  `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions) et BM25 français, vecteurs
  nommés `dense` et `bm25` dans Qdrant, requête `query_points` à deux `prefetch` fusionnés
  par RRF, filtre optionnel par règlement.
- Construction idempotente de l'index : identifiant `uuid5` stable par chunk, collection
  nommée `vigie_<id embedding>_<empreinte corpus>`, collection complète jamais recalculée,
  point d'entrée `screen` qui met en quarantaine les chunks signalés (garde-fou du J4).
- Commande `vigie-index` et script `python -m scripts.retrieval_demo` qui affiche le top-5
  de trois questions.
- Sous-commande `vigie-eval retrieval` : recall@k et MRR sur une partie du jeu de
  référence, `dev` par défaut, articles distincts.
- `open_retriever` choisit la recherche Qdrant ou les passages fixes selon
  `VIGIE_RETRIEVER` ; `python -m vigie.rag.cli` passe par Qdrant sans `--passages`.
- Réglages `VIGIE_QDRANT_PATH`, `VIGIE_COLLECTION_PREFIX`, `VIGIE_QDRANT_COLLECTION`,
  `VIGIE_SPARSE_LANGUAGE`, `VIGIE_EMBEDDING_CACHE_DIR`, `VIGIE_RETRIEVAL_PREFETCH_LIMIT`,
  `VIGIE_RETRIEVAL_RRF_K`, `VIGIE_RETRIEVER`, `VIGIE_STATIC_PASSAGES_PATH`, décrits dans
  `.env.example`, et documentation `docs/retrieval.md`.
- Preuves du jalon dans `docs/proofs/J2/` : recall@5 0,638 et MRR 0,486 sur les 47
  questions `dev`, sous le seuil de 0,80 et 0,60, jalon noté `PARTIEL`.

### Changed

- Réglage `VIGIE_COLLECTION` remplacé par `VIGIE_COLLECTION_PREFIX`, le nom complet de la
  collection étant désormais dérivé du modèle et du corpus.

## [0.9.0] - 2026-10-06

### Added

- Infrastructure Oracle Always Free du jalon J14 (`infra/terraform/`) : nœud A1 avec
  cloud-init durci et k3s épinglé, réseau dédié, budget à zéro euro avec alerte au premier
  centime, bucket de sauvegarde purgé après 30 jours.
- Tests qui figent les invariants de sécurité et de coût du code Terraform.
- Masquage des OCID, IP publiques, adresses e-mail, clé SSH, namespace et préfixe du
  domaine de disponibilité dans les sorties d'infrastructure (`vigie.infra.redact`).
- Tâche `python tasks.py infra-retry` qui relance la création du nœud A1 en cas de manque
  de capacité, toutes les 10 minutes pendant sept jours avant le repli k3d.
- Réglages `VIGIE_INFRA_*`, décrits dans `.env.example`, et preuves masquées du jalon dans
  `docs/proofs/J14/`.

## [0.8.0] - 2026-10-06

### Added

- Red teaming automatisé du jalon J10 (`redteam/`) : 360 attaques générées par promptfoo
  0.123.1 avec le Ministral local, 60 par famille, puis triées par `curate.py` en un
  fichier de rejeu déterministe `redteam/attacks.generated.yaml`.
- Rejeu `redteam/replay.yaml` contre l'API désignée par `VIGIE_REDTEAM_BASE_URL`, et
  `redteam/score.py` qui juge le taux d'attaques réussies contre le seuil de 5 % et
  indique ce qui a arrêté chaque attaque défendue.
- Tâche `python tasks.py redteam` et réglage `VIGIE_REDTEAM_MAX_ATTACK_SUCCESS_RATE`,
  décrits dans `.env.example`.
- Documentation `docs/redteam.md` et preuves du jalon dans `docs/proofs/J10/` (barrière
  verte sur un bouchon protégé, vue rouge sur un bouchon qui fuit et sur un jeton faux).

### Changed

- `types-PyYAML` ajouté aux dépendances de développement, `redteam` déclaré comme paquet
  interne pour le tri des imports.

## [0.7.0] - 2026-10-06

### Added

- Préparation du test de charge du jalon J11 : scénario Locust `load/locustfile.py` avec
  trois profils (usage normal, attaquant, rafale), questions tirées du jeu de référence
  avec repli intégré, et verdict calculé en fin de run contre le p95, le taux d'erreur et
  la part d'injections non bloquées.
- Garde-fou de charge : run refusé sans `VIGIE_LOAD_TOKEN`, refusé au-delà de 8
  utilisateurs vers un hôte qui n'est pas la machine locale, interface web de Locust
  refusée.
- Tâche `python tasks.py load-local` pour le protocole local (20 utilisateurs, 5 minutes,
  rapport dans `results/load/`).
- Seuils de charge écrits avant mesure dans la section `load` de `eval/thresholds.yaml`,
  avec un test qui fait échouer la construction si les valeurs par défaut de `Settings`
  s'en écartent.
- Documentation `docs/load-test.md` et preuves du câblage sur un bouchon local dans
  `docs/proofs/J11/`.
- Réglages `VIGIE_LOAD_*`, décrits dans `.env.example`.

### Changed

- `pyyaml` déclaré dans les dépendances de développement, dont le test du fichier de seuils
  a besoin.

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
