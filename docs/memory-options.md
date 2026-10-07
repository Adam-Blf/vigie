# Options mémoire des pods de l'API

Mesures du 7 octobre 2026 pour arbitrer l'architecture mémoire des pods de l'API. Ce
document mesure, il ne tranche pas : la décision reste à prendre, avec les arbitrages
listés en fin de page.

Le point de départ est connu ([architecture.md](architecture.md#budget-mémoire-sur-12-go)) :
le pod de l'API mesuré au J7 tient 975 Mio, au-dessus du budget de 950 Mio par pod
(`dense_embedding.max_pod_rss_mib` de `eval/thresholds.yaml`, branche `feat/evaluation`) et
de la `limit` de 640 Mio du manifeste, et la pile au pic atteint 8,7 Go pour un plafond de
8,5 Go. Côté qualité, seul e5-base int8 par canal (run o de
[evaluation.md](https://github.com/Adam-Blf/vigie/blob/feat/evaluation/docs/evaluation.md),
la configuration l passée en int8 par canal) franchit les planchers de rappel sur `dev`,
et il avait échoué sur la mémoire, mesurée sous Windows.

## Protocole

- **Conteneurs Linux** construits par `deploy/docker/api.Dockerfile`, lancés par
  `docker compose` avec la surcharge
  [compose.mem.yml](proofs/J8/memory-options/compose.mem.yml) : un projet Compose par
  configuration, des volumes à part, la pile `vigie` et ses volumes jamais touchés.
- **Deux images.** `mem-main` est `origin/main` (pile du J7, dense fastembed). `mem-merged`
  est `origin/main` fusionnée en local avec `feat/evaluation` (dense int8, garde anglais,
  poids dense 3), fusion jamais poussée ; seule différence de construction, les deux
  contrôles hors ligne du Dockerfile tournent en fp32, les fichiers int8 du J12 étant montés
  en lecture seule plutôt que copiés dans l'image (même mémoire une fois chargés).
- **Mesure** par [measure.py](proofs/J8/memory-options/measure.py) : 20 questions par
  `POST /v1/ask` avec le LLM factice, puis `docker stats --no-stream`, les fichiers cgroup
  v2 (`memory.current`, `memory.peak`, `memory.stat`) et `VmRSS`/`VmHWM` du processus.
  Une seconde passe de 20 questions donne la latence à chaud. Aucune question du split
  `test`, aucun fichier scellé lu.
- **Réglages** injectés sans toucher au code par un `sitecustomize.py` monté
  ([probe/](proofs/J8/memory-options/probe/)), inactif quand ses variables sont vides.
- Sorties brutes dans [proofs/J8/memory-options/raw/](proofs/J8/memory-options/raw/),
  environnement et provenance des images dans `raw/environment.txt`.

**Convention du total.** Même calcul que `architecture.md`, pour rester comparable à son
8,7 Go : les autres composants valent 5,78 Go (k3s 1,2 estimé, Ollama 3,5 mesuré, Qdrant
0,05, MLflow 0,43, Prometheus 0,4 estimé, Argo et Flux 0,2 estimés, web 0,003), auxquels
s'ajoutent 3 pods d'API (HPA 2 plus 1 canary), les Mio comptés comme des Mo.

## Tableau des options

Pod de l'API : `docker stats` après les 20 questions, au repos ; entre parenthèses le pic
cgroup (`memory.peak`) pendant le chargement, ce que la `limit` doit couvrir.

| Option | RSS du pod de l'API | Pile au pic, plafond 8,5 Go | recall@5 / MRR `dev` | Latence ajoutée | Complexité | Ce qui change dans `deploy/k8s` |
|---|---|---|---|---|---|---|
| A. Statu quo J7, MiniLM fastembed (`main`) | 978 Mio (pic 1 130) | 8,71 Go, au-dessus de 0,21 ; 7,74 Go à 2 pods | 0,638 / 0,486 (run a) | référence | nulle | `limits.memory` 640Mi vers 1200Mi environ, `requests` 512Mi vers 1000Mi ; `maxReplicas` 3 vers 2 pour tenir 8,5 Go |
| A2. MiniLM int8 du J12 branché (run d) | 832 Mio (pic 969) | 8,28 Go, sous le plafond | 0,638 / 0,509 (run d) | aucune ; l'embedding seul passe de 30 à 8 ms | faible : fusion de `feat/evaluation`, fichier int8 (119 Mo) dans l'image | `limits.memory` vers 1024Mi, `requests` vers 850Mi ; réindexation par le Job (nouvel identifiant de collection) |
| B. e5-base int8 par canal, chunks de 350 mots, garde anglais, poids 3 (run o) | 992 Mio (pic 1 128) | 8,76 Go, au-dessus de 0,26 ; 7,76 Go à 2 pods | **0,809 / 0,655** (run o) | aucune mesurable | moyenne : fusion, fichier int8 (279 Mo) dans l'image, réindexation, référence de dérive à réparer | comme A, plus `VIGIE_DENSE_MODEL`, `VIGIE_DENSE_MAX_TOKENS=512`, `VIGIE_CORPUS_SPLIT_WORDS=350` pour l'API et le Job d'ingestion ; `limit` du Job à revoir |
| C. Réglages bon marché sur A ou B | aucun réglage ne gagne plus de 10 Mio | inchangée | inchangés | nulle | faible | variables d'environnement seulement, pour rien |
| D. Service `vigie-models` partagé, API sans modèle | 113 Mio (pic 177), plus `vigie-models` 951 Mio (A, B) ou 796 Mio (A2) | 7,07 Go (A ou B), 6,92 Go (A2) ; 8,02 Go avec 2 répliques de `vigie-models` (B) | ceux du modèle hébergé, donc 0,809 / 0,655 avec B | environ 3 ms par appel, 2 appels par question, soit 5 à 10 ms | élevée : un service de plus, un client HTTP dans l'API, un point de panne unique | nouveau Deployment, Service et NetworkPolicy `vigie-models` ; API à `requests` 128Mi, `limits` 256Mi |

Les planchers de `eval/thresholds.yaml` sont 0,80 de recall@5 et 0,60 de MRR : seules B et
D hébergeant e5-base les franchissent sur `dev`. Les chiffres de rappel viennent des runs
existants de `evaluation.md`, rien n'a été réévalué ici.

## A. Le statu quo confirmé et décomposé

Le J7 mesurait 975 Mio ; la même image refaite donne **978 Mio**, puis 980, 979 et 982 sur
trois relances ([raw/A.txt](proofs/J8/memory-options/raw/A.txt)). Le pic cgroup monte à
1 122 à 1 130 Mio pendant le chargement des modèles. Avec la `limit` actuelle de 640 Mio, le
pod serait tué au démarrage.

Décomposition par [breakdown.py](proofs/J8/memory-options/probe/breakdown.py), un second
processus qui charge la même chose dans le même ordre que l'API (VmRSS, Mio) :

| Étape | A, MiniLM fastembed | A2, MiniLM int8 | B, e5-base int8 |
|---|---|---|---|
| Python seul | 14 | 14 | 14 |
| Modules de l'API importés (FastAPI, pydantic, qdrant-client, fastembed, onnxruntime) | +123 | +123 | +122 |
| Session ONNX du modèle dense | **+559** | **+408** | **+563** |
| BM25 (fastembed) | +0 | +0 | +1 |
| Session ONNX du garde-fou DeBERTa int8 | **+316** | **+320** | **+321** |
| Référence de dérive, client Qdrant, une recherche | +10 | +9 | +10 |
| **Total** | **1 024** | **874** | **1 031** |

Lecture :

- **Les deux sessions ONNX font 83 à 86 % du pod.** Le tas Python, numpy compris, pèse 64 Mio
  en tout (`tracemalloc`, [raw/A-breakdown-trace.txt](proofs/J8/memory-options/raw/A-breakdown-trace.txt)) :
  le reste est de la mémoire native d'ONNX Runtime.
- **Une session pèse bien plus que son fichier.** MiniLM int8 : fichier de 119 Mo, session
  de 408 Mio. e5-base int8 : 279 Mo pour 563 Mio. Garde-fou : 244 Mo pour 320 Mio. Les
  matrices d'embedding des deux modèles denses sont stockées en uint8 dans les fichiers
  (vérifié dans le graphe) ; d'où vient l'écart n'est pas établi ici.
- **Le total du second processus dépasse le pod** de 40 à 50 Mio : VmRSS compte les pages
  partagées des bibliothèques, que `docker stats` (mémoire anonyme du cgroup) ne compte pas.

## B. e5-base int8 dans un conteneur Linux

**992 Mio** au repos, 989 et 990 aux relances, pic cgroup 1 124 à 1 128 Mio
([raw/B.txt](proofs/J8/memory-options/raw/B.txt)). Sous Windows le même pod mesurait
1 019 Mio : Linux rend 27 Mio, ce qui laisse **42 Mio au-dessus** du budget de 950 Mio.
MiniLM int8 suit le même écart (864 Mio sous Windows, 832 Mio ici).

Deux constats en passant :

- **La référence de dérive ne se construit pas avec e5-base** : `vigie-drift
  build-reference` charge le modèle dense par fastembed, qui ne connaît pas
  `multilingual-e5-base`. Le Job d'ingestion échoue donc à sa dernière étape ; l'API a été
  lancée sans suivi de dérive pour cette mesure (moins de 1 Mio d'écart).
- **L'indexation e5-base demande beaucoup plus que le Job ne permet** : un relevé
  ponctuel de `docker stats` pendant l'indexation donne 4,3 Gio pour le conteneur
  d'ingestion ([raw/ingest-o-snapshot.txt](proofs/J8/memory-options/raw/ingest-o-snapshot.txt)),
  quand `ingest-job.yaml` lui donne 768Mi. Relevé unique, pas un pic mesuré.

## C. Réglages bon marché, chacun mesuré

Chaque réglage relance le pod seul, sur A puis sur B, avec le même protocole
([raw/A.txt](proofs/J8/memory-options/raw/A.txt), [raw/B.txt](proofs/J8/memory-options/raw/B.txt)) :

| Réglage | A (base 978 Mio) | B (base 992 Mio) |
|---|---|---|
| C1. Sessions ONNX sans arène mémoire CPU | 977 | 987 |
| C2. Sessions sans pré-empaquetage des poids | 978 | 989 |
| C3. `intra_op_num_threads` à 1 | 977 | 989 |
| C4. Les trois ensemble | 978 | 986 |
| C5. `MALLOC_ARENA_MAX=2` | 979 | 988 |
| C6. jemalloc 5.3 en `LD_PRELOAD` | 980 | 989 |
| C7. C4, C5 et C6 ensemble | 977 | 983 |
| Base relancée (stabilité) | 982 | 990 |
| C8. Optimisations de graphe coupées (processus de décomposition) | +69 | +21 |

- **Aucun réglage ne bouge le pod de plus de 10 Mio**, soit l'ordre du bruit entre deux
  relances. La mémoire est celle des poids chargés, pas de la fragmentation de l'allocateur.
  Le J7 et la branche `feat/evaluation` avaient trouvé la même chose (5 Mio).
- **Couper les optimisations de graphe aggrave** de 21 à 69 Mio
  ([raw/C8-graph-opt-off.txt](proofs/J8/memory-options/raw/C8-graph-opt-off.txt)).
- **Workers uvicorn** : l'API lance `uvicorn.run(app)` avec l'objet application, donc un
  seul processus par construction. Il n'y a rien à retirer ; deux workers chargeraient
  chacun leurs modèles.
- **Imports paresseux** : les imports coûtent 123 Mio
  ([raw/A-imports.txt](proofs/J8/memory-options/raw/A-imports.txt)), mais tous servent au
  chemin d'une question. Le seul module inutile est `grpc` (20 Mio), importé par
  `qdrant-client` lui-même : le différer demanderait de modifier la bibliothèque. Gain
  plafond 20 Mio, non mesuré dans le pod.
- Le réglage déjà en place, `MALLOC_TRIM_THRESHOLD_` (270 Mio rendus au J7), reste le seul
  qui ait compté.

## D. Modèles partagés : un service `vigie-models`

Un service tient l'embedder (dense et BM25) et le garde-fou, et répond en HTTP aux pods de
l'API ([models_service.py](proofs/J8/memory-options/probe/models_service.py), maquette
sans authentification ni lot). Les pods de l'API remplacent leurs modèles par des appels
HTTP (même `sitecustomize.py`). Les réponses restent les mêmes : l'identifiant d'embedding,
donc la collection Qdrant, vient du service.

| Modèle hébergé | Pod de l'API sans modèle | `vigie-models` | Total au pic, 3 pods d'API |
|---|---|---|---|
| A, MiniLM fastembed | 112 à 117 Mio (pic 177) | 944 à 951 Mio (pic 1 090) | 7,07 Go |
| A2, MiniLM int8 | 113 Mio (pic 163) | 796 Mio (pic 931) | 6,92 Go |
| B, e5-base int8 | 113 à 114 Mio (pic 174) | 951 Mio (pic 1 085) | 7,07 Go |

Sorties : [raw/D.txt](proofs/J8/memory-options/raw/D.txt),
[raw/A-D.txt](proofs/J8/memory-options/raw/A-D.txt).

**Latence du saut supplémentaire**, mesurée de l'intérieur du pod de l'API par
[hop.py](proofs/J8/memory-options/probe/hop.py), 100 appels après 10 de chauffe
([raw/hop.txt](proofs/J8/memory-options/raw/hop.txt)) : `GET /healthz`, le saut seul, prend
2,5 à 3,2 ms en médiane et 4 à 10 ms au p95. Une question fait deux appels (embedding,
garde-fou), soit 5 à 10 ms de plus. Sur `POST /v1/ask` complet, la différence se perd dans
le bruit du poste partagé : médianes à chaud de 77 à 150 ms en distant
contre 75 à 140 ms en local. Mesure grossière, sur une seule machine, sans réseau réel ni
kube-proxy.

**Un incident** : une réponse 500 sur environ 300 questions passées en mode distant (A,
première manche), non reproduite à la relance, cause non capturée. La maquette n'a ni
nouvelle tentative ni délai court ; un vrai client en aurait besoin.

## Arbitrages

Rien n'est choisi ici. Ce que chaque option achète et ce qu'elle coûte :

- **A, statu quo avec limites relevées.** Ne demande rien de nouveau, mais ne tient
  8,5 Go qu'à 2 pods d'API (HPA 1 plus le canary, ou HPA 2 sans canary simultané), et le
  rappel reste sous les planchers (0,638 contre 0,80).
- **A2, MiniLM int8.** Tient 3 pods sous 8,5 Go avec 0,22 Go de marge et sous les 950 Mio
  par pod, mais pas sous les 0,7 Go du brief, et le rappel reste sous les planchers. Le
  plus petit pas pour remettre la pile dans le budget.
- **B, e5-base int8.** Seule option à passer les planchers de qualité sur `dev`. Dépasse
  950 Mio par pod de 42 Mio et 8,5 Go de 0,26 Go à 3 pods ; tient à 2 pods (7,76 Go). Exige
  de réparer la référence de dérive et de revoir la `limit` du Job d'ingestion.
- **C, réglages.** Mesurés sans effet : ils ne changent le verdict d'aucune option.
- **D, service partagé.** Découple la mémoire du nombre de pods : chaque pod d'API ajouté
  coûte 113 Mio au lieu d'un Go, ce qui laisse e5-base tenir avec 3 pods (7,07 Go) et
  même 2 répliques de `vigie-models` (8,02 Go). En échange : un service de plus à
  construire, sécuriser (NetworkPolicy, authentification entre pods) et superviser ; un
  point de panne unique avec une seule réplique ; un CPU d'inférence partagé que l'HPA de
  l'API ne fait pas grandir ; 5 à 10 ms par question ; un changement de modèle dense qui
  devient un déploiement de `vigie-models` au lieu d'un canary de l'API (le brief, 11.8,
  ne fait porter le canary que sur le prompt ou `top_k`, ce qui reste compatible).
- **Combinaisons.** B à 2 pods et D avec B sont les deux façons mesurées de garder les
  planchers de qualité dans 8,5 Go ; la première coûte du débit, la seconde de la
  complexité.

## Reproduire

Depuis la racine du dépôt, avec `VIGIE_QDRANT_API_KEY`, `MEM_TAG`, `PROBE_DIR`,
`QUANT_DIR` et `EXTRA_DIR` posés (voir l'en-tête de `compose.mem.yml`) :

```
docker compose -p vigiemem-main -f docker-compose.yml \
  -f docs/proofs/J8/memory-options/compose.mem.yml up -d api
python docs/proofs/J8/memory-options/measure.py "A" vigiemem-main-api-1 8711
docker exec vigiemem-main-api-1 python /probe/breakdown.py
```

Les réglages de la section C sont des variables d'environnement passées au même
`up -d --no-deps --force-recreate api` ; le service partagé se lance avec
`--profile shared-models` et `VIGIE_PROBE_REMOTE_MODELS=http://models:8800`.
