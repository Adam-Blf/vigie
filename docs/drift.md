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
Stephens) pour ne pas embarquer scipy dans l'image de l'API. Sur une grande fenêtre, il
devient très sensible : le seuil `VIGIE_DRIFT_KS_ALPHA` se règle si des alertes
apparaissent sans changement visible des deux autres indicateurs.

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

1. Au démarrage, `DriftMonitor.from_settings(settings, DriftMetrics(registry, bundle_version))`.
2. Après chaque réponse, `monitor.record(embedding)` avec l'embedding déjà calculé pour la
   recherche, sans le texte.
3. `GET /v1/admin/drift` renvoie `monitor.evaluate().to_dict()`.

## Preuve

`python scripts/drift_demo.py` construit la référence avec le vrai modèle, injecte
30 questions DORA puis 30 questions de cuisine, et affiche le rapport et les métriques à
chaque étape. Sortie enregistrée dans `docs/proofs/J9/`.
