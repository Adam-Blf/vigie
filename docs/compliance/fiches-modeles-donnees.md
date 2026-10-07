# Fiches des modèles et des données

Une fiche par modèle et par jeu de données qu'utilise Vigie, au format des *model cards* et
*data cards* : à quoi il sert ici, ce qui est épinglé, sous quelle licence, ce qu'on a
mesuré et où il échoue. Licences relevées le 7 octobre 2026 sur les sources primaires (API
Hugging Face, couche licence des manifestes Ollama, avis juridique d'EUR-Lex) ; l'inventaire
complet, paquets compris, est dans [`THIRD_PARTY_LICENSES.md`](../../THIRD_PARTY_LICENSES.md).

Aucun poids de modèle n'est versionné dans le dépôt (`git ls-files` ne contient ni
`.onnx`, ni `.gguf`, ni `.safetensors`) : les modèles sont téléchargés au build de l'image ou
au déploiement, depuis leur source, à une révision épinglée.

## Modèles en production

### Ministral 3 3B Instruct (LLM)

| Champ | Valeur |
|---|---|
| Usage dans Vigie | rédiger la réponse à partir des passages récupérés, sans outil ni mémoire |
| Épinglage | `ministral-3:3b-instruct-2512-q4_K_M` (`src/vigie/config.py:74`), quantification Q4_K_M retenue au J12 (`docs/quantization.md`) |
| Fournisseur | Mistral AI, servi en local par Ollama ; aucune question ne sort de la VM |
| Licence | Apache 2.0 : carte Hugging Face `mistralai/Ministral-3-3B-Instruct-2512` (`license: apache-2.0`) et couche licence du manifeste Ollama (texte Apache 2.0). Usage, modification et redistribution permis, avec la licence et les mentions jointes |
| Données d'entraînement | non publiées par Mistral AI : **limite**, impossible d'auditer ce que le modèle a vu |
| Mesuré | premier token à 60 s et réponse en 271 s sur le poste, six réponses sur dix sans citation au J12 (`docs/quantization.md`, `docs/proofs/J7/`) |
| Garde-fous autour | citations vérifiées contre le corpus et retirées si inventées, refus quand rien ne répond, contrôle de sortie contre la fuite du prompt (`docs/redteam.md`) |

### ProtectAI DeBERTa v3 base, injection de prompt v2 (garde-fou d'entrée)

| Champ | Valeur |
|---|---|
| Usage dans Vigie | classer la question comme injection ou non, après la règle regex |
| Épinglage | révision `90c9989b1a342275dd0d1a95aad283c04e075671` (`src/vigie/config.py:145`), exporté en ONNX int8 par canal au build (`src/vigie/guard/prepare.py`) |
| Licence | Apache 2.0 (carte `protectai/deberta-v3-base-prompt-injection-v2`) ; modèle de base `microsoft/deberta-v3-base` sous MIT |
| Données d'entraînement | sept jeux publics listés sur la carte, dont `jackhhao/jailbreak-classification`, `Harelix/Prompt-Injection-Mixed-Techniques-2024`, `OpenSafetyLab/Salad-Data` ; majoritairement en anglais |
| Mesuré | rappel 1,0 sur les injections directes FR et EN, 0 % de faux positifs, p95 96 ms sur la partie `test` (`docs/guardrails-benchmark.md`, `docs/proofs/J4/guard/`) |
| Limite | entraîné en anglais : en français, la règle regex porte une partie du travail ; un contournement inédit reste possible (`docs/risk-map.md`, LLM01) |

### paraphrase-multilingual-MiniLM-L12-v2 (embedding dense, dérive)

| Champ | Valeur |
|---|---|
| Usage dans Vigie | vecteur dense de la recherche hybride et fenêtre de dérive (J9) |
| Épinglage | révision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` (`src/vigie/config.py:227`), variante int8 (`src/vigie/config.py:224`) |
| Licence | Apache 2.0 (carte `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) |
| Mesuré | recall@5 0,638 et MRR 0,486 en hybride sur `dev` (`docs/retrieval.md`) ; int8 : taille divisée par 4 (`docs/quantization.md`) |
| Limite | contexte coupé à 128 jetons (`src/vigie/config.py:228`) : les longs articles sont résumés par leur début ; seuil de recherche du brief non atteint (J2 `PARTIEL`) |

### Qdrant BM25 (vecteur creux)

| Champ | Valeur |
|---|---|
| Usage dans Vigie | branche lexicale de la recherche hybride, racinisation française |
| Épinglage | `Qdrant/bm25` (`src/vigie/config.py:40`), langue `french` (`src/vigie/config.py:42`) |
| Licence | Apache 2.0 (carte `Qdrant/bm25`) |
| Limite | pas de révision épinglée dans la configuration : les fichiers sont ceux que fastembed télécharge au build de l'image, figés ensuite dans la couche du modèle |

## Modèles du banc d'essai (jamais livrés)

| Modèle | Licence | Ce que la licence impose ici |
|---|---|---|
| `fastino/gliguard-LLMGuardrails-300M` | Apache 2.0 | rien de plus : mesuré sur le poste, non redistribué |
| `llama-guard3:1b` (Meta Llama Guard 3 1B) | Llama 3.2 Community License (carte Hugging Face, accès soumis à acceptation ; couche licence Ollama) | politique d'usage acceptable de Meta ; mention « Built with Llama » et copie de la licence **seulement en cas de redistribution**, ce que Vigie ne fait pas. La restriction visant les personnes établies dans l'UE porte sur les modèles multimodaux de Llama 3.2, pas sur ce modèle texte |
| Lakera Guard (API) | conditions d'utilisation de Lakera | seuls les jeux publics lui ont été envoyés, jamais une question d'utilisateur (`src/vigie/config.py:208`) |

## Données

### Corpus réglementaire (EUR-Lex)

| Champ | Valeur |
|---|---|
| Contenu | DORA, AI Act, RGPD, AMLR, en français, versions publiées au JO (CELEX dans `NOTICE`) |
| Source | Cellar, Office des publications, en HTTPS (`src/vigie/config.py:57`) |
| Intégrité | empreinte SHA-256 et nombre d'articles par texte dans `data/corpus.lock` (`docs/corpus.md`) |
| Conditions | « © Union européenne », réutilisation autorisée, à des fins commerciales ou non, avec mention de la source (décision 2011/833/UE, articles 6 et 7 ; avis juridique d'EUR-Lex, rubrique *Copyright notice*). La même rubrique place les **textes consolidés** sous CC BY 4.0 avec indication des modifications : Vigie n'indexe que les actes d'origine (CELEX `3...`), pas les consolidés (`0...`) |
| Transformations | découpage par article, normalisation des espaces et des listes, contenu inchangé ; dit dans `NOTICE` et sur la page À propos |
| Données personnelles | aucune |
| Interdit | le logo EUR-Lex sans accord de l'Office des publications : Vigie ne l'utilise pas |

### Jeu de référence et graines du benchmark

| Champ | Valeur |
|---|---|
| Contenu | 80 questions rédigées par le binôme et vérifiées contre Cellar (`data/golden/`), graines du benchmark des garde-fous (`data/seed.jsonl`) |
| Licence | celle du dépôt (`LICENSE`), auteurs Adam Beloucif et Emilien Morice |
| Intégrité | partie `test` scellée par empreinte (`data/golden/test.sha256`), vérifiée en CI |
| Données personnelles | aucune ; les exemples de données personnelles des graines sont fictifs |

### deepset/prompt-injections

| Champ | Valeur |
|---|---|
| Usage | contrôle externe du benchmark J4, téléchargé au moment de la mesure |
| Licence | Apache 2.0 (carte du jeu sur Hugging Face) |
| Limite | langue des exemples non déclarée sur la carte du jeu ; quota gratuit Lakera épuisé en cours de mesure (`docs/progress.md`, J4) |
