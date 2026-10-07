# Détection de drift

Le module `src/vigie/drift/` surveille les questions posées en production et signale
quand elles s'éloignent de ce que Vigie sait traiter. Il ne conserve que des vecteurs :
le texte des questions n'entre jamais dans la fenêtre glissante.

## Principe

La référence se compose de deux matrices enregistrées en `.npy` :

- `reference.npy`, les embeddings des questions du jeu de référence ;
- `anchors.npy`, les centroïdes du corpus, un par règlement (DORA, AIACT, RGPD, AMLR),
  calculés par `group_centroids` à partir des embeddings des passages.

Chaque question de production passe par le même modèle d'embedding que la recherche
(`VIGIE_DENSE_MODEL`, MiniLM multilingue par défaut), puis rejoint une fenêtre bornée
(`EmbeddingWindow`). Toutes les `VIGIE_DRIFT_EVALUATE_EVERY` questions, le moniteur
recalcule trois indicateurs.

| Indicateur | Ce qu'il mesure | Alerte si |
|---|---|---|
| `centroid_distance` | distance cosinus entre le centroïde de la référence et celui de la fenêtre | supérieure à `VIGIE_DRIFT_CENTROID_THRESHOLD` (0,3) |
| `out_of_scope_ratio` | part des questions dont la similarité au centroïde du corpus le plus proche reste sous `VIGIE_DRIFT_OUT_OF_SCOPE_SIMILARITY` (0,3) | supérieure à `VIGIE_DRIFT_OUT_OF_SCOPE_RATIO` (0,25) |
| `ks_pvalue` | test de Kolmogorov-Smirnov à deux échantillons entre les similarités de la référence et celles de la fenêtre | inférieure à `VIGIE_DRIFT_KS_ALPHA` (0,01) |

Tant que la fenêtre compte moins de `VIGIE_DRIFT_MIN_WINDOW` questions (30), le rapport
est marqué `ready: false` et ne lève aucune alerte : un test statistique sur une poignée
de points ne mesure que du bruit.

Le test de Kolmogorov-Smirnov est écrit avec numpy (valeur p asymptotique, correction de
Stephens) pour ne pas embarquer scipy dans l'image de l'API.

### Limite connue : la marge du test KS est mince

Sur la preuve J9, le lot de 30 questions DORA reste sous le seuil, mais de peu : la
statistique KS vaut 0,302 et la valeur p 0,088, pour un seuil de 0,01. La référence
mélange les quatre règlements alors que le lot ne parle que de DORA, et cette seule
différence de répartition suffit à écarter les deux distributions de similarité.

Avec une référence de 34 questions, l'écart D qu'il faut atteindre pour passer sous
`VIGIE_DRIFT_KS_ALPHA` = 0,01 se resserre quand la fenêtre grossit :

| Taille de la fenêtre | D critique (alpha 0,01) | D critique (alpha 0,001) |
|---|---|---|
| 30 | 0,395 | 0,475 |
| 150 | 0,305 | 0,365 |
| 500 | 0,285 | 0,340 |

Conséquence : un trafic légitime mais concentré sur un seul règlement, avec le même écart
que le lot DORA, déclencherait une alerte `ks_test` seule à partir d'environ 150
questions dans la fenêtre, alors que la distance entre centroïdes et la part hors
périmètre restent basses. Le test d'intégration ne couvre que des lots de 30 questions
et ne prouve donc pas l'absence de fausse alerte sur une fenêtre pleine.

Pistes, à trancher avec le jeu de référence réel (J8) : reconstruire la référence sur le
jeu `data/golden/` (au moins 80 questions, ce qui réduit le bruit côté référence),
abaisser `VIGIE_DRIFT_KS_ALPHA` à 0,001, ou ne compter une alerte `ks_test` qu'en
présence d'un second indicateur. Une alerte `ks_test` isolée se lit d'abord comme un
changement de répartition entre règlements, pas comme une dérive hors sujet.

## Construire la référence

```bash
python tasks.py drift-reference
# équivalent, une fois le paquet installé :
vigie-drift build-reference
```

La commande écrit `data/drift/reference.npy` et `data/drift/anchors.npy` (chemins
`VIGIE_DRIFT_REFERENCE_PATH` et `VIGIE_DRIFT_ANCHORS_PATH`, ou `--reference-out` et
`--anchors-out`) avec le modèle `VIGIE_DENSE_MODEL` (ou `--model`).

- Questions : `data/golden/questions.jsonl`, en ne gardant que les lignes `in_scope`,
  `verified` et hors du découpage `test` ; le jeu scellé ne sert jamais à régler quoi
  que ce soit. Sans ce fichier, la commande retombe sur `tests/fixtures/drift_questions.json`.
  `--questions` force une autre source (`.jsonl` lu comme le jeu de référence, sinon
  comme la fixture).
- Ancres : un centroïde par règlement, calculé sur les chunks de `data/corpus/*.jsonl`
  (champs `regulation` et `text`). Sans corpus, la commande retombe sur les passages de
  la fixture. `--corpus` (répétable) désigne un fichier ou un dossier précis.

La sortie indique la source réellement utilisée, ce qui évite de livrer par mégarde une
référence construite sur la fixture.

## Alerte

Une alerte produit deux signaux :

- un log structuré JSON sur le logger `vigie.drift`, niveau `WARNING`, événement
  `drift_alert`, émis une seule fois au début de l'incident ; l'événement
  `drift_recovered` (niveau `INFO`) en marque la fin ;
- la jauge `vigie_drift_alert` à 1.

## Métriques Prometheus

Toutes portent le label `bundle_version` : `vigie_drift_centroid_distance`,
`vigie_drift_out_of_scope_ratio`, `vigie_drift_ks_pvalue`, `vigie_drift_alert`.
`DriftMetrics` reçoit le registre à utiliser ; l'API lui passera celui qu'elle sert sur
le port 9711.

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `VIGIE_DRIFT_REFERENCE_PATH` | `data/drift/reference.npy` | embeddings des questions de référence |
| `VIGIE_DRIFT_ANCHORS_PATH` | `data/drift/anchors.npy` | centroïdes du corpus |
| `VIGIE_DRIFT_WINDOW_SIZE` | 500 | taille maximale de la fenêtre glissante |
| `VIGIE_DRIFT_MIN_WINDOW` | 30 | taille minimale avant tout jugement |
| `VIGIE_DRIFT_EVALUATE_EVERY` | 10 | réévaluation automatique toutes les N questions |
| `VIGIE_DRIFT_CENTROID_THRESHOLD` | 0,3 | seuil de distance entre centroïdes |
| `VIGIE_DRIFT_OUT_OF_SCOPE_SIMILARITY` | 0,3 | similarité sous laquelle une question est hors périmètre |
| `VIGIE_DRIFT_OUT_OF_SCOPE_RATIO` | 0,25 | part tolérée de questions hors périmètre |
| `VIGIE_DRIFT_KS_ALPHA` | 0,01 | seuil de la valeur p du test KS |

Les seuils ont été calibrés sur MiniLM multilingue : les questions réglementaires se
situent au-dessus de 0,3 de similarité au centroïde le plus proche, les questions de
cuisine autour de 0.

## Raccordement à l'API (J5)

Branché au J7 dans `src/vigie/api/drift.py` :

1. Au démarrage, `load_monitor` charge la référence si `reference.npy` et `anchors.npy`
   existent ; sinon la surveillance est coupée avec un avertissement et
   `GET /v1/admin/drift` répond 503 `drift_unavailable`. Une référence d'une autre
   dimension que l'embedder est refusée de la même façon.
2. L'embedder du retriever est enveloppé (`DriftTap`) : le vecteur dense déjà calculé pour
   la recherche part aussi dans la fenêtre, sans seconde inférence et sans le texte. Une
   question bloquée par les garde-fous n'atteint pas le retriever, donc pas la fenêtre.
   Une erreur d'enregistrement est journalisée, jamais remontée : la dérive ne coûte
   jamais une réponse.
3. Les jauges `vigie_drift_*` rejoignent le registre de l'API, servies par `/metrics`.
4. `GET /v1/admin/drift` (jeton `admin`, 403 pour `user`) renvoie
   `monitor.evaluate().to_dict()`.

Dans `docker compose`, le job `ingest` construit la référence une fois, après
l'indexation, sur le volume `/data` que l'API lit.

## Tests

`python tasks.py test` lance les tests unitaires avec un faux embedder déterministe ; les
tests marqués `integration`, qui téléchargent et exécutent le vrai MiniLM, sont exclus
par défaut (`addopts` de `pyproject.toml`). Pour les lancer :

```bash
python tasks.py test-integration
# ou directement
python -m pytest -m integration
```

## Preuve

`python scripts/drift_demo.py` construit la référence avec le vrai modèle, injecte
30 questions DORA puis 30 questions de cuisine, et affiche le rapport et les métriques à
chaque étape. Sortie enregistrée dans `docs/proofs/J9/`.
