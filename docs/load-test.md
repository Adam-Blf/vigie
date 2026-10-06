# Test de charge

Ce document décrit le protocole du test de charge de `POST /v1/ask` et accueille ses
résultats. Le scénario vit dans `load/locustfile.py`, la logique qui peut se tromper
(garde de sécurité, lecture des questions, verdict) dans `src/vigie/loadtest/`, testée
sans lancer Locust.

## Ce que l'on mesure

On mesure notre pile, c'est-à-dire l'authentification, les garde-fous et la recherche.
La vitesse du LLM n'entre pas dans ce test : sur un processeur Arm, Ministral 3B produit
quelques jetons par seconde et écraserait tout le reste. L'API tourne donc toujours avec
`VIGIE_LLM_PROVIDER=fake` pendant la charge. La latence du vrai modèle est mesurée à part,
sur la VM.

## Profils

| Profil | Poids | Comportement |
|---|---|---|
| Utilisateur normal | 7 | une question du jeu de référence `data/golden/`, puis 1 à 3 s de lecture |
| Attaquant | 2 | une injection parmi une liste fixe, puis 2 à 5 s de pause |
| Rafale | 1 | cinq questions d'affilée, puis 8 à 12 s de silence |

Tant que `data/golden/` n'existe pas, le profil normal puise dans une courte liste intégrée
de questions en français et en anglais. Les attaques ont leur propre ligne dans le rapport,
`/v1/ask [attack]`, parce qu'une requête bloquée répond plus vite et flatterait le p95 du
chemin de réponse.

## Seuils

Les seuils sont écrits une seule fois, dans la section `load` de `eval/thresholds.yaml`,
à côté des seuils d'évaluation. L'API les lit par `Settings`, dont les valeurs par défaut
doivent rester égales au fichier : `tests/loadtest/test_load_thresholds_file.py` fait
échouer la CI si les deux divergent. Abaisser un seuil est une décision écrite dans un
ADR, jamais la réparation d'un run rouge.

| Mesure | Seuil | Clé de `eval/thresholds.yaml` | Réglage ponctuel |
|---|---|---|---|
| p95 de `/v1/ask` (hors attaques) | strictement sous 500 ms | `load.p95_ms` | `VIGIE_LOAD_P95_MS` |
| Taux d'erreur, toutes requêtes | strictement sous 1 % | `load.max_error_ratio` | `VIGIE_LOAD_MAX_ERROR_RATIO` |
| Injections non bloquées | au plus 10 % des attaques jugées | `load.max_attack_leak_ratio` | `VIGIE_LOAD_MAX_ATTACK_LEAK_RATIO` |
| Utilisateurs contre un hôte non local | au plus 8 | `load.remote_max_users` | aucun, constante du code |

Le dernier seuil est le complément du rappel minimal de 0,90 exigé des garde-fous. Une
injection qui passe ne compte pas comme une erreur HTTP : c'est un défaut de qualité du
garde-fou, jugé à part, et le mélanger aux erreurs rendrait les deux chiffres illisibles.

À la fin du run, le verdict fixe le code de sortie du processus. Un seuil manqué donne
le code 1, comme un test rouge, et chaque dépassement est écrit dans la sortie.

## Garde de sécurité

Un tir trop lourd contre une production partagée a déjà coupé un site pendant
vingt-cinq minutes sur un autre projet. Le scénario refuse donc de démarrer, avant la
première requête, dans quatre cas :

- l'hôte n'est ni `localhost` ni une adresse de bouclage et le run demande plus de
  8 utilisateurs (chaque utilisateur Locust garde au plus une requête en vol) ;
- aucun hôte n'est donné ;
- `VIGIE_LOAD_TOKEN` est absent ;
- Locust est lancé avec son interface web, où l'hôte et le nombre d'utilisateurs se
  modifient après le contrôle.

Le plafond de 8 est une constante du code et pas un réglage : c'est précisément la valeur
qu'on serait tenté de remonter dans l'urgence. Contre la production, on se limite à une
vérification de vie. La recherche de limite se fait en local, ou sur la VM avant son
ouverture au public.

Un tunnel vers la production compte comme la production. Un `ssh -L`, un
`kubectl port-forward` ou tout autre transfert de port qui fait apparaître l'API déployée
sur `127.0.0.1` trompe la garde, qui ne voit que l'adresse locale : le plafond de
8 utilisateurs s'applique quand même, et c'est à la personne qui lance le run de le
respecter. La garde ne protège que contre l'erreur de bonne foi, pas contre son
contournement.

## Protocole local

1. Créer un jeton de test pour l'API locale et le placer dans `VIGIE_LOAD_TOKEN`, sans
   l'afficher ni le committer.
2. Lancer l'API en local avec `VIGIE_LLM_PROVIDER=fake`. Relever pour ce run
   `VIGIE_RATE_LIMIT_PER_MINUTE` et `VIGIE_DAILY_QUOTA`, sinon un seul jeton partagé par
   20 utilisateurs bute sur la limite de débit et le test mesure le 429, pas la pile.
3. Installer l'extra de charge : `uv pip install --python .venv -e ".[load]"`.
4. Lancer `python tasks.py load-local`. La tâche envoie 20 utilisateurs pendant 5 minutes
   sur `http://127.0.0.1:<VIGIE_PORT>` et écrit le rapport HTML et les CSV dans
   `results/load/`. Les arguments ajoutés passent à Locust après les valeurs par défaut,
   par exemple `python tasks.py load-local -t 30s` pour un essai court.
5. Copier `report.html`, `load_stats.csv` et la sortie console dans
   `docs/proofs/J11/`, avec le `manifest.json` du run.

## Résultats

Les mesures réelles arrivent quand l'API (J5) est fusionnée. Le tableau sera rempli avant
et après le passage à l'échelle horizontal de J13.

| Configuration | Utilisateurs | Durée | p50 (ms) | p95 (ms) | Débit (req/s) | Erreurs | Injections non bloquées | Verdict |
|---|---|---|---|---|---|---|---|---|
| Local, 1 réplique, faux LLM | 20 | 5 min | à mesurer | à mesurer | à mesurer | à mesurer | à mesurer | à mesurer |
| k3s, HPA, faux LLM | 20 | 5 min | à mesurer | à mesurer | à mesurer | à mesurer | à mesurer | à mesurer |

### Vérification du câblage

Avant la fusion de J5, le scénario a été lancé contre un bouchon HTTP local
(`docs/proofs/J11/stub_api.py`) qui répond instantanément sans recherche ni LLM. Ce run
prouve que les profils, le jeton, le rapport et le verdict fonctionnent ; ses chiffres ne
disent rien des performances de Vigie et ne doivent pas être cités comme tels. Les sorties
brutes sont rangées dans `docs/proofs/J11/`.

### Coût du générateur de charge

Ce même run donne une mesure qui compte pour la suite : contre un bouchon qui répond
instantanément, avec 20 utilisateurs, Locust sur le poste Windows de développement
mesure déjà environ 410 ms au p95 de `/v1/ask` (médiane 77 ms). Ce temps est celui du
générateur, pas du service : Locust et l'API se partagent le même processeur, et la boucle
d'événements de Locust sous Windows ajoute sa propre attente. Le générateur seul consomme
donc plus des quatre cinquièmes du budget de 500 ms avant que Vigie ait fait quoi que ce
soit.

Un run lancé depuis ce poste contre une API locale ne peut donc pas juger le seuil de p95
de façon honnête. Les mesures du tableau ci-dessus se prennent avec Locust hors du poste
Windows, de deux façons :

- sur la VM Linux, avant son ouverture au public, Locust visant l'API de la VM sur
  `127.0.0.1` : c'est le seul cadre où les 20 utilisateurs du protocole sont permis ;
- depuis une autre machine Linux vers l'API de la VM : la garde voit alors un hôte non
  local et plafonne le run à 8 utilisateurs, ce qui suffit à comparer avec le run sur la
  VM et à isoler le coût du générateur.

Le poste Windows reste bon pour vérifier le câblage et pour un essai court.
