# ADR 0003. LLM open-weight servi en local

- **Statut** : accepté
- **Date** : 2026-10-02
- **Auteurs** : Emilien Morice, Adam Beloucif

## Contexte

La proposition de sujet prévoyait un LLM open-weight « hébergé en Europe ou en local »,
avec l'API Mistral comme piste naturelle pour un projet de conformité européen. Depuis
2026, l'offre gratuite de Mistral ne délivre plus de clé d'API : les clés sont réservées
au mode Pay-as-you-go, avec carte bancaire. L'ADR 0001 exclut toute dépense.

Il reste donc à servir le modèle soi-même, sur une VM Arm de 2 OCPU et 12 Go partagée
avec tout le reste du système (ADR 0002). Le modèle doit être assez petit pour tenir dans
environ 3 Go, assez bon en français pour reformuler un article de règlement, et publié
sous une licence qui autorise l'usage et la démonstration publique.

## Décision

Vigie utilise **Ministral 3 3B Instruct**, quantifié en **Q4_K_M**, servi par **Ollama**
sur la VM, sous l'étiquette épinglée :

```
ministral-3:3b-instruct-2512-q4_K_M
```

Vérification faite le 2 octobre 2026 sur le registre Ollama : le manifeste de cette
étiquette répond HTTP 200, la couche de poids pèse 2 953 825 504 octets (environ 2,95 Go)
et la couche de licence contient le texte de l'Apache License 2.0. L'étiquette est
reprise telle quelle dans `src/vigie/config.py` (`ollama_model`) et dans le bundle MLflow.

Règles associées :

- **Une seule instance Ollama**, partagée par tous les pods de l'API, avec
  `OLLAMA_NUM_PARALLEL=1` et une file bornée (`OLLAMA_MAX_QUEUE` faible). File pleine :
  l'API répond 503 avec `Retry-After` au lieu d'empiler les requêtes.
- **Faux LLM** (`VIGIE_LLM_PROVIDER=fake`) pour les tests, la charge et le red teaming en
  CI. Le fournisseur se choisit par configuration, jamais par un en-tête HTTP.
- **Streaming** de la réponse vers l'interface (SSE), pour que l'attente se voie.
- L'étiquette du modèle ne change pas pendant un canary : la démonstration fait varier le
  prompt ou `top_k`, pas le LLM.
- L'adaptateur pour l'API Mistral peut exister dans `src/vigie/llm/` pour comparaison,
  mais il n'est jamais le fournisseur par défaut ni celui de la production.

## Conséquences

- **Souveraineté renforcée.** Aucune question, aucun passage du corpus et aucune réponse
  ne quittent la VM. Il n'y a aucun fournisseur de LLM tiers à déclarer dans le registre
  des traitements, ce qui simplifie aussi la page Confidentialité.
- **Latence.** Sur CPU Arm, le modèle produit quelques tokens par seconde. La cible publiée
  est un premier token sous 5 s et une réponse de 300 tokens sous 60 s, mesurés sur la VM.
  `num_predict` est plafonné pour borner le pire cas.
- **Mémoire.** Le budget réserve 3,0 Go à Ollama. Les poids seuls en prennent déjà
  2,95 Go, sans compter le cache KV pour un contexte de 4 096 tokens. Ce poste est le plus
  exposé du tableau : il sera mesuré à la conteneurisation (J7), et s'il déborde, le
  contexte sera réduit avant toute autre mesure.
- **Qualité.** Un modèle de 3 milliards de paramètres se trompe plus qu'un grand modèle.
  La validation des citations, le refus quand aucun passage ne répond et la barrière
  d'évaluation compensent en partie ; les scores publiés sont ceux de ce modèle, sans
  arrondi favorable.
- **Quantization.** Q4_K_M est le point de départ. L'étude de J12 compare Q4_K_M et Q8_0
  (premier token, débit, mémoire, qualité sur le jeu de référence) avant de figer le choix.
- **Licence.** Apache 2.0 : usage, modification et démonstration publique autorisés. Les
  poids ne sont jamais copiés dans le dépôt ; Ollama les télécharge au démarrage.
