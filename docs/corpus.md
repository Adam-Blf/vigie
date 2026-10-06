# Corpus réglementaire

Vigie indexe quatre règlements européens, téléchargés depuis Cellar, le référentiel de
l'Office des publications de l'Union européenne, en HTTPS uniquement.

| Code  | Règlement                    | CELEX       |
|-------|------------------------------|-------------|
| DORA  | Règlement (UE) 2022/2554     | 32022R2554  |
| AIACT | Règlement (UE) 2024/1689     | 32024R1689  |
| RGPD  | Règlement (UE) 2016/679      | 32016R0679  |
| AMLR  | Règlement (UE) 2024/1624     | 32024R1624  |

La mention de la source et les conditions de réutilisation figurent dans `NOTICE`.

## Commande `vigie-ingest`

La commande est déclarée dans `pyproject.toml` (`[project.scripts]`) et devient disponible
après l'installation du paquet :

```sh
uv pip install --python .venv -e ".[dev]"
vigie-ingest --help
```

Elle télécharge chaque texte, vérifie son empreinte contre `data/corpus.lock`, découpe le
texte par article et écrit un fichier JSONL par règlement dans `data/corpus/`.

| Option             | Effet                                                                      |
|--------------------|----------------------------------------------------------------------------|
| `--only CODE`      | limite l'ingestion à un règlement, répétable (`--only DORA --only RGPD`)   |
| `--recitals`       | indexe aussi les considérants, exclus par défaut                           |
| `--update-lock`    | enregistre ce qui vient d'être téléchargé dans le fichier de verrou        |
| `--lock CHEMIN`    | fichier de verrou à utiliser, `data/corpus.lock` par défaut                |
| `--out DOSSIER`    | dossier de sortie des JSONL, `data/corpus` par défaut                      |
| `--from-url URL`   | lit un corpus JSONL déjà publié au lieu d'interroger Cellar                |

Codes de sortie : `0` succès, `1` échec de téléchargement ou écart avec le verrou, `2`
erreur d'usage (code de règlement inconnu, verrou absent, `--from-url` combiné à
`--update-lock`).

## Verrou du corpus

`data/corpus.lock` fige, pour chaque règlement, le CELEX, l'empreinte sha256 du XHTML, le
nombre d'articles et la date de téléchargement. Une ingestion ordinaire s'arrête dès que le
CELEX, l'empreinte ou le nombre d'articles diffère : un texte modifié côté EUR-Lex ne peut
pas entrer dans l'index sans une mise à jour explicite du verrou avec `--update-lock`, relue
puis commitée.

Le corpus publié lu par `--from-url` est contrôlé sur le CELEX et le nombre d'articles du
verrou, faute de XHTML source pour recalculer l'empreinte.

## Paramètres

Les réglages se lisent dans `vigie.config.Settings` et se surchargent par variables
d'environnement préfixées `VIGIE_` (par exemple `VIGIE_CORPUS_CACHE_DIR`) : URL de Cellar
et hôte autorisé, langue (`fra`), dossier de cache (`data/cache`), intervalle minimal d'une
seconde entre deux requêtes, nombre de tentatives et délai de repli, délai d'attente, nombre
maximal de redirections, taille de découpage des articles longs.

## Preuves

Les exécutions réelles du jalon J1 sont consignées dans `docs/proofs/J1/`, avec la commande
de chaque fichier dans `manifest.json`.
