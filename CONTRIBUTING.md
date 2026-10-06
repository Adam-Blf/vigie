# Contribuer à Vigie

Vigie est développé en binôme par Adam Beloucif et Emilien Morice. Ces règles valent pour
chaque commit, y compris les plus petits. Elles existent pour qu'un relecteur puisse faire
confiance à l'historique sans le refaire.

## Mise en place

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[dev]"
.venv/Scripts/python -m pre_commit install
```

Le hook de co-auteur (voir plus bas) n'est pas géré par pre-commit : il s'installe à la
main dans `.git/hooks/prepare-commit-msg`, et `pre-commit install` ne doit pas recevoir
`--hook-type prepare-commit-msg`, qui l'écraserait.

Sous Linux ou macOS, remplacer `.venv/Scripts/python` par `.venv/bin/python`. Les tâches du
projet passent par `python tasks.py <tâche>`, sans script `.bat` ni `.ps1`.

## Branches

- `main` ne reçoit jamais de commit direct. Seul le commit racine y a été créé.
- Une branche par jalon ou par sujet, préfixée par sa nature : `feat/`, `fix/`, `docs/`,
  `chore/`, `test/`, `ci/`. Exemple : `feat/retrieval`.
- Fusion par `git merge --no-ff`, avec un message `merge: <sujet>`.
- Une branche jetable `test/gate-<nom>` sert à montrer qu'une barrière échoue sur une
  entrée dégradée ; elle est supprimée ensuite.

## Commits

- **Conventional Commits en anglais**, à l'impératif, courts :
  `feat(rag): add hybrid retriever with RRF fusion`.
- Un commit porte un seul changement cohérent, testé. Plusieurs petits commits valent
  mieux qu'un seul énorme.
- Horodatage réel uniquement : on ne modifie jamais `GIT_AUTHOR_DATE` ni
  `GIT_COMMITTER_DATE`, et on ne réécrit pas un historique déjà poussé.
- Jamais de `--no-verify`. Si un hook échoue, on corrige la cause.
- Aucune ligne de signature d'outil automatique dans les messages.

### Identités et co-auteur

L'identité est passée à chaque commit, jamais par `git config --global` :

```sh
git -c user.name="Adam Beloucif" -c user.email="adam.beloucif@efrei.net" commit -m "..."
git -c user.name="Emilien Morice" -c user.email="261297658+emilien754@users.noreply.github.com" commit -m "..."
```

**Chaque commit crédite les deux membres du binôme.** Le hook
`.git/hooks/prepare-commit-msg` ajoute automatiquement l'autre membre en co-auteur :

```
Co-authored-by: Emilien Morice <261297658+emilien754@users.noreply.github.com>
Co-authored-by: Adam Beloucif <adam.beloucif@efrei.net>
```

Le premier trailer apparaît sur les commits d'Adam, le second sur ceux d'Emilien. On le
vérifie après chaque commit avec `git log -1 --format=%B`. S'il manque, on recrée le hook
avec ce contenu, puis on le rend exécutable :

```sh
#!/bin/sh
# Pair work on one machine: every commit credits the other half of the pair.
author=$(git var GIT_AUTHOR_IDENT | sed 's/ <.*//')
case "$author" in
  "Adam Beloucif") partner="Emilien Morice <261297658+emilien754@users.noreply.github.com>" ;;
  "Emilien Morice") partner="Adam Beloucif <adam.beloucif@efrei.net>" ;;
  *) exit 0 ;;
esac
name=${partner%% <*}
if ! grep -q "Co-authored-by: $name" "$1"; then
  git interpret-trailers --in-place --trailer "Co-authored-by: $partner" "$1"
fi
```

Un job de CI vérifiera aussi que chaque commit d'une branche porte un co-auteur du binôme
(jalon J15). Les auteurs alternent par lot cohérent, pour que l'historique reflète le
travail réel de chacun.

## Barrières de qualité

Avant chaque commit, tout doit être vert :

```sh
python tasks.py check    # ruff check, ruff format --check, mypy src, pytest avec couverture
python tasks.py typo     # caractères interdits dans les fichiers du dépôt
```

Le pre-commit lance aussi ruff, la correction des fins de fichier, la détection de clé
privée et gitleaks. La CI rejoue ruff, mypy et pytest sur chaque pull request.

Seuils de couverture : au moins 80 % sur `src/`, au moins 95 % sur `guard`,
`rag/citations.py`, `api/auth`, `api/usage` et `drift`. Un seuil ne se baisse jamais pour
faire passer un jalon ; ce serait une décision écrite dans un ADR.

Pour qu'une barrière compte, il faut l'avoir vue échouer au moins une fois sur une entrée
volontairement dégradée. La sortie de ce run rouge est rangée dans `docs/proofs/gates/`.

## Code

- Python typé, `mypy` en mode strict sur `src/`. Front-end en TypeScript uniquement.
- **Un fichier, une responsabilité.** Au-delà de 300 lignes de code, on se demande ce qui
  peut sortir ; au-delà de 500, le découpage est obligatoire. Les données générées ne
  sont pas concernées.
- Toute valeur réglable vit dans `src/vigie/config.py`, avec un test. Aucune valeur en dur
  dupliquée ailleurs.
- Les commentaires expliquent pourquoi, jamais ce que le code dit déjà.
- Pas de `TODO` ni de `FIXME` livré, pas de code mort, pas de dépendance inutilisée. Ce qui
  doit attendre devient une ligne de `docs/progress.md`.
- Tout bug corrigé arrive avec un test écrit avant le correctif et vu rouge.

## Textes et typographie

- Les textes destinés à un humain (documentation, interface, rapport) sont en français
  correct et accentué, relus deux fois. Le code, les identifiants et les commits sont en
  anglais.
- Ni tiret long, ni demi-cadratin, ni point médian, nulle part. On utilise le tiret court,
  la virgule ou le point. `python tasks.py typo` les détecte, ainsi que les caractères
  invisibles (espaces de largeur nulle, marques bidirectionnelles, BOM).

## Sécurité

- Aucun secret dans le dépôt, les commits, les journaux ou les captures. Les fichiers
  `.env` et `terraform.tfvars` sont ignorés ; `.env.example` ne contient aucune valeur
  réelle.
- Aucune IP de VM, aucun OCID, aucun jeton dans la documentation ni dans `docs/proofs/`.
- Les services locaux se lient à `127.0.0.1`. Ports réservés : API 8710, interface 4710,
  Qdrant 6733 et 6734, MLflow 5710, Prometheus 9710.
- Une vulnérabilité se signale en privé aux auteurs, jamais dans une issue publique.

## Preuves

Chaque jalon range sa preuve dans `docs/proofs/J<n>/` : un `manifest.json` (SHA du
commit, date, commande exacte, versions des outils) et les sorties brutes, sans secret.
