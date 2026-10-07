# Progression

Une ligne par jalon fusionné. Reprise après interruption : repartir du premier jalon qui
n'est pas `DONE`. Statuts possibles : `DONE`, `PARTIEL`, `BLOQUÉ`.

| Date | Jalon | Statut | Preuve | Motif | Suite |
|---|---|---|---|---|---|
| 2026-10-02 | J0 outillage | DONE | `docs/proofs/J0/` (check vert, co-auteurs) | | cadrage en cours sur `docs/framing` |
| 2026-10-02 | J0 cadrage | DONE | `docs/proofs/J0-cadrage/` (check vert, typo vert et vu rouge, mypy tests) | | jalons de construction à partir du corpus |
| 2026-10-02 | J1 corpus | DONE | `docs/proofs/J1/` (ingestion réelle, verrou vu rouge sur l'empreinte et le nombre d'articles, couverture) | | indexation hybride dans Qdrant |
| 2026-10-02 | J3 LLM et RAG | DONE | `docs/proofs/J3/` (trois réponses réelles de Ministral 3B, citation inventée retirée, couverture 99 %) | | brancher la recherche Qdrant à la place des passages fixes ; seuil de latence mesuré sur la VM au J7 et au J14 |
| 2026-10-02 | J8 jeu de référence | DONE | `docs/proofs/J8/` (80 questions vérifiées contre Cellar, partie test scellée, validateur vert puis vu rouge sur brouillons et copie dégradée) | | mesure réelle contre les seuils de `eval/thresholds.yaml` au J11, quand l'API répond de bout en bout |
| 2026-10-06 | J4 benchmark des garde-fous | DONE | `docs/proofs/J4/bench/` (six garde-fous sur le jeu maison `test` et le contrôle deepset, suivi MLflow) | quota gratuit Lakera épuisé sur deepset, 20 exemples sur 116 mesurés pour cet outil | chaîne de garde-fous de production sur `feat/guard` ; latences à refaire sur la VM |
| 2026-10-06 | J5 API sécurisée | DONE | `docs/proofs/J5/` (curl sans jeton 401, avec jeton 200 et réponse citée, injections FR et EN bloquées, question piège acceptée, usage, SSE, 403, 413, 422, chaîne d'audit intacte ; faux LLM et Ministral 3B local) | `/readyz` à 503 une fois avec Ollama occupé, délai de sonde porté de 2 à 5 s | relancer J11 contre l'API ; exposer le drift du J9 sous `/v1/admin` ; brancher le bundle de la CD au J13 |
| 2026-10-06 | J4 chaîne de garde-fous | DONE | `docs/proofs/J4/guard/` (regex puis DeBERTa ONNX int8 sur l'anglais : rappel injections directes 1,0 FR et EN, 0 % de faux positifs, p95 96 ms sur `test`) | deux itérations : la quantification int8 par tenseur cassait le classifieur (rappel EN 0,75), corrigée par la quantification par canal ; p95 de 252 ms sur `dev` avec la machine chargée | brancher la chaîne dans l'API (J5) ; latence à mesurer sur la VM au J7 et au J14 |
| 2026-10-06 | J9 détection de drift | DONE | `docs/proofs/J9/` (aucune alerte sur 30 questions DORA, trois alertes après 30 questions hors sujet, tests d'intégration avec le vrai MiniLM) | marge du test KS mince sur le lot DORA (p 0,088 pour un seuil de 0,01), documentée dans `docs/drift.md` | exposer `GET /v1/admin/drift` avec l'API au J5 |
| 2026-10-06 | J11 test de charge | PARTIEL | `docs/proofs/J11/` (garde-fous de charge vus rouges, verdict vu rouge, 20 utilisateurs pendant 60 s contre un bouchon local) | mesure réelle impossible tant que l'API du J5 n'est pas fusionnée ; les latences du bouchon ne disent rien de Vigie | lancer `python tasks.py load-local` contre l'API locale dès le J5 et juger contre la section `load` de `eval/thresholds.yaml` |
| 2026-10-06 | J10 red teaming | PARTIEL | `docs/proofs/J10/` (360 attaques générées en local, barrière verte sur un bouchon protégé, vue rouge sur un bouchon qui fuit et sur un jeton faux) | rejeu contre la vraie API impossible tant que le J5 n'est pas fusionné | rejouer en CI contre l'API avec le faux LLM, puis à la main contre Ministral, dès le J5 |
| 2026-10-06 | J14 infrastructure Oracle (première moitié) | BLOQUÉ | `docs/proofs/J14/` (plan et apply masqués, réseau, budget, bucket et politique IAM créés, journal d'`infra-retry`) | VM A1 refusée par Oracle, « Out of host capacity » en eu-paris-1 | `infra-retry` relance toutes les 10 minutes ; repli k3d (décision 6) au bout de sept jours |
| 2026-10-07 | J2 recherche hybride | PARTIEL | `docs/proofs/J2/` puis `docs/proofs/J8/eval/` (configuration retenue au J8, MiniLM int8, garde anglais, poids dense 3 : recall@5 0,638 et MRR 0,509 sur `dev`, mesurée une fois sur `test` : recall@5 0,652 [0,435 ; 0,826], MRR 0,514 [0,344 ; 0,692] ; e5-base int8 par canal en chunks de 350 mots : 0,809 et 0,655 sur `dev`, `pod-rss.txt`) | seuils de recherche (0,80 et 0,60) non atteints sur `test` avec ce qui tient dans le pod de l'API ; e5-base int8 par canal passe les planchers sur `dev`, la parité et la taille, mais le pod de l'API monte à 1 019 Mio pour 950 permis (règle `dense_embedding` écrite avant la mesure), et l'option sans préempaquetage ni arène ONNX Runtime ne gagne que 5 Mio | décision d'Adam (ADR) : pod d'embedding séparé, ou budget revu (par exemple 2 pods d'API au lieu de 3), puis mesure unique de `test` pour e5-base ; brancher le garde-fou d'entrée sur `screen` au J4 |
| 2026-10-06 | J13 Kubernetes, canary et scaling | PARTIEL | `docs/proofs/J13/` (kubeconform sur 5 couches, budget vert puis vu rouge, essais côté serveur, surcouche dev appliquée sur k3d) | images de l'API et de l'interface pas encore publiées, le canary n'a donc pas tourné avec du trafic réel | rejouer le canary et l'autoscaling dès que la CI publie les images (J5, J7, J15) |
| 2026-10-06 | J15 CI/CD GitHub Actions | PARTIEL | `docs/proofs/J15/` et `docs/proofs/gates/` (actionlint, crédit du binôme, planchers de couverture et épinglage vus rouges), CI de la PR verte | portes d'évaluation, de red teaming et de l'interface inactives faute de `vigie-eval gate`, de `docker-compose.yml` et de `web/` ; aucune image publiée tant que les Dockerfile n'existent pas | elles démarrent seules avec le J8 (porte), le J7 (Docker) et le J6 (interface) |
| 2026-10-06 | J12 quantization | DONE | `docs/proofs/J12/` (seuil écrit avant mesure, parité ONNX contre PyTorch 7,5e-8, embedding int8 retenu sur `dev` : taille x 0,25, rappel@5 0,468 puis 0,511, barrière vue rouge sur un seuil dégradé ; Ministral Q4_K_M contre Q8_0 sur CPU, Q4_K_M gardé) | | premier token mesuré à 60 s sur le poste : à mesurer sur la VM au J14 contre le seuil de 5 s ; six réponses sur dix sans citation dans les deux variantes, à reprendre avec la recherche hybride du J2 ; brancher `dense_variant` dans l'embedder dense de `vigie.retrieval`, qui charge encore le modèle par fastembed |
| 2026-10-06 | J6 interface PWA | PARTIEL | `docs/proofs/J6/` (build et budget JS, 93 tests unitaires, contraste clair et sombre, 54 tests Playwright dont axe et CSP de production) | Lighthouse jamais lancé, interface testée contre une API simulée | lancer `npm run --prefix web lhci`, puis rejouer la suite Playwright contre l'API du J5, désormais fusionnée |
| 2026-10-07 | J8 évaluation, MLflow et choix du modèle | PARTIEL | `docs/proofs/J8/eval/` (`vigie-eval run`, `gate`, `register`, `alias` ; 15 configurations comparées sur `dev`, un run MLflow chacune, capture de l'interface ; export int8 par canal d'e5-base, parité fp32 2,2e-7, fichier x 0,251 ; mémoire du pod de l'API mesurée, 864 Mio pour MiniLM et 1 019 Mio pour e5-base ; barrière vue rouge sur `test` et sur une configuration dégradée dans `docs/proofs/gates/` ; enregistrement refusé par la barrière) | aucune version `vigie-rag` enregistrée : la configuration retenue ne passe pas les planchers de recherche sur `test`, et e5-base, qui les passe sur `dev`, dépasse la mémoire du pod ; le job CI `eval-gate` est rouge pour la même raison, la PR #24 reste ouverte | enregistrer le premier champion dès qu'une configuration passe la barrière dans le budget ; décision d'Adam sur la mémoire (voir J2) ; juge LLM hors CI (DeepEval) encore à faire ; mémoire du pod à remesurer dans le conteneur Linux du J7 |

## Décisions par défaut appliquées (section 10 du brief)

| # | Décision | Valeur retenue | Origine |
|---|---|---|---|
| 4 | Visibilité du dépôt | public depuis le 2026-10-06 (historique scanné par gitleaks, aucun secret, OCID ni IP), fusion par PR uniquement, `main` protégée | Adam, 2026-10-06 |
| 12 | Publication avec le nom de l'école | dépôt public, accord de l'enseignant obtenu, mention « projet de cours, sujet rédigé par le binôme » | Adam, 2026-10-06 |
| 14 | Clé Lakera | fournie par Adam, stockée hors dépôt | Adam, 2026-10-02 |

## Reste à faire

Suivi détaillé jalon par jalon dans le tableau ci-dessus. Les points en attente d'une
décision d'Adam sont listés dans la section 10 du brief.

- **Contexte du LLM trop long (mesuré au J8).** Avec la recherche retenue, les 6 passages
  font en médiane 2 280 mots et le prompt environ 3 850 jetons pour un `num_ctx` de 4 096 ;
  24 prompts `dev` sur 54 dépassent la fenêtre (`docs/proofs/J8/eval/context-size.txt`).
  C'est une cause probable des 3 réponses sur 10 avec citation et du premier token à 60 s
  du J12. À traiter côté prompt et pipeline (moins de passages ou passages coupés), puis à
  remesurer avec Ollama.
- **Fichier int8 dans l'image de l'API.** La recherche lit désormais
  `data/quant/<modèle>/model-int8.onnx` (`VIGIE_DENSE_VARIANT=int8`), un fichier non
  versionné : l'image Docker du J7 doit l'embarquer (export `vigie-quant export --models`
  dans l'étape de build, ou téléchargement épinglé), et l'index doit être reconstruit avec
  la même variante, puisque le nom de collection change.
- **Modèle dense inchangé.** MiniLM-L12 reste le modèle déployé ; la mesure fp32 contre int8
  du J12 reste valable et la calibration du drift (J9) aussi. Si un modèle e5 est adopté
  après la décision mémoire, le J12 et le drift sont à remesurer sur ce modèle.
