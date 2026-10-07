# Licences des composants tiers

Fichier généré par `scripts/third_party_licenses.py`, ne pas modifier à la main. Sources :
`pip-licenses` sur l'environnement d'exécution de l'API (Linux, `uv sync --frozen`, sans
extra), la liste des paquets npm réellement présents dans le build de l'interface
(`web/scripts/third-party-licenses.ts`) et `docs/compliance/licences.yaml` pour les modèles,
jeux de données et services, chacun avec sa source primaire.

Le code de Vigie reste sous la licence propriétaire de `LICENSE`. Aucun composant livré n'est
sous copyleft fort ; la CI le vérifie à chaque PR (job `licenses`). Les modèles et jeux de
données ne sont jamais copiés dans le dépôt.

## Modèles

| Nom | Épinglage | Rôle | Licence | Livraison | Source |
|---|---|---|---|---|---|
| mistralai/Ministral-3-3B-Instruct-2512 | Ollama ministral-3:3b-instruct-2512-q4_K_M (src/vigie/config.py:74) | LLM de production, servi par Ollama sur la VM | Apache-2.0 | téléchargé au déploiement par Ollama, jamais dans le dépôt | https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512 (carte : license apache-2.0) ; couche licence du manifeste Ollama : texte Apache 2.0 |
| protectai/deberta-v3-base-prompt-injection-v2 | révision 90c9989b1a342275dd0d1a95aad283c04e075671 (src/vigie/config.py:145) | classifieur d'injection du garde-fou d'entrée, exporté en ONNX int8 | Apache-2.0 | intégré à l'image de l'API au build, jamais dans le dépôt | https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2 (license apache-2.0, modèle de base microsoft/deberta-v3-base sous MIT) |
| sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | révision e8f8c211226b894fcb81acc59f3b34ba3efd5f42 (src/vigie/config.py:227) | embedding dense de la recherche et de la détection de dérive | Apache-2.0 | intégré à l'image de l'API au build, jamais dans le dépôt | https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (license apache-2.0) |
| Qdrant/bm25 | src/vigie/config.py:40 | modèle creux BM25 (mots vides et racinisation) de la recherche hybride | Apache-2.0 | intégré à l'image de l'API au build, jamais dans le dépôt | https://huggingface.co/Qdrant/bm25 (license apache-2.0) |
| fastino/gliguard-LLMGuardrails-300M | src/vigie/config.py:199 | benchmark des garde-fous (J4) seulement | Apache-2.0 | jamais livré, banc d'essai sur le poste | https://huggingface.co/fastino/gliguard-LLMGuardrails-300M (license apache-2.0) |
| meta-llama/Llama-Guard-3-1B | Ollama llama-guard3:1b (src/vigie/config.py:200) | benchmark des garde-fous (J4) seulement | Llama 3.2 Community License | jamais livré ni redistribué, banc d'essai sur le poste | https://huggingface.co/meta-llama/Llama-Guard-3-1B (license llama3.2, accès soumis à acceptation) ; couche licence du manifeste Ollama : LLAMA 3.2 COMMUNITY LICENSE AGREEMENT |

## Jeux de données et textes

| Nom | Épinglage | Rôle | Licence | Livraison | Source |
|---|---|---|---|---|---|
| deepset/prompt-injections | src/vigie/config.py:197 | contrôle externe du benchmark des garde-fous (J4) | Apache-2.0 | téléchargé au moment du benchmark, jamais dans le dépôt | https://huggingface.co/datasets/deepset/prompt-injections (license apache-2.0) |
| Jeu de référence data/golden et graines data/seed.jsonl | data/golden/test.sha256 | évaluation (J8) et benchmark (J4) | rédigés par le binôme, sous la licence du dépôt (LICENSE) | dans le dépôt | data/golden/questions.jsonl, data/seed.jsonl |
| Règlements DORA, AI Act, RGPD, AMLR (EUR-Lex, Cellar) | data/corpus.lock (empreinte SHA-256 par texte) | corpus indexé | réutilisation autorisée avec mention de la source, décision 2011/833/UE, articles 6 et 7 | téléchargé à l'ingestion, jamais dans le dépôt | https://eur-lex.europa.eu/content/legal-notice/legal-notice.html (Copyright notice) ; CELEX 32011D0833 |

## Services et images

| Nom | Rôle | Licence | Source |
|---|---|---|---|
| Qdrant (image qdrant/qdrant) | base vectorielle | Apache-2.0 | https://github.com/qdrant/qdrant |
| Ollama (image ollama/ollama) | serveur du LLM local | MIT | https://github.com/ollama/ollama |
| nginx-unprivileged (image nginxinc/nginx-unprivileged) | serveur de l'interface | BSD-2-Clause (nginx), Apache-2.0 (recette de l'image) | https://github.com/nginx/nginx ; https://github.com/nginxinc/docker-nginx-unprivileged |
| MLflow | suivi d'expériences | Apache-2.0 | https://github.com/mlflow/mlflow |
| Lakera Guard (API distante) | benchmark des garde-fous (J4) seulement, sur les jeux publics, jamais sur une question d'utilisateur | conditions d'utilisation de Lakera (service propriétaire) | https://www.lakera.ai/terms-of-service |

## Paquets Python de l'API (53)

| Paquet | Version | Licence | Source |
|---|---|---|---|
| annotated-doc | 0.0.5 | MIT | https://github.com/fastapi/annotated-doc |
| annotated-types | 0.8.0 | MIT | https://github.com/annotated-types/annotated-types |
| anyio | 4.15.1 | MIT | https://anyio.readthedocs.io/en/stable/versionhistory.html |
| beautifulsoup4 | 4.15.0 | MIT License | https://www.crummy.com/software/BeautifulSoup/bs4/ |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) | https://github.com/certifi/python-certifi |
| charset-normalizer | 3.5.2 | MIT | https://github.com/jawah/charset_normalizer/blob/master/CHANGELOG.md |
| click | 8.5.0 | BSD-3-Clause | https://github.com/pallets/click/ |
| fastapi | 0.142.2 | MIT | https://github.com/fastapi/fastapi |
| fastembed | 0.8.1 | Apache Software License | https://github.com/qdrant/fastembed |
| filelock | 4.0.12 | MIT | https://github.com/tox-dev/py-filelock |
| flatbuffers | 25.12.19 | Apache Software License | https://google.github.io/flatbuffers/ |
| fsspec | 2026.9.0 | BSD-3-Clause | https://github.com/fsspec/filesystem_spec |
| grpcio | 1.84.0 | Apache-2.0 | https://grpc.io |
| h11 | 0.16.0 | MIT License | https://github.com/python-hyper/h11 |
| h2 | 4.4.1 | MIT | https://github.com/python-hyper/h2/ |
| hf-xet | 1.6.0 | Apache-2.0 | https://github.com/huggingface/xet-core |
| hpack | 4.2.0 | MIT | https://github.com/python-hyper/hpack/ |
| httpcore | 1.0.9 | BSD-3-Clause | https://www.encode.io/httpcore/ |
| httptools | 0.8.0 | MIT | https://github.com/MagicStack/httptools |
| httpx | 0.28.1 | BSD License | https://github.com/encode/httpx |
| huggingface_hub | 1.33.0 | Apache Software License | https://github.com/huggingface/huggingface_hub |
| hyperframe | 6.1.0 | MIT License | https://github.com/python-hyper/hyperframe/ |
| idna | 3.20 | BSD-3-Clause | https://github.com/kjd/idna |
| loguru | 0.7.3 | MIT License | https://github.com/Delgan/loguru |
| lxml | 6.1.3 | BSD-3-Clause | https://lxml.de/ |
| mmh3 | 5.3.1 | MIT License | https://pypi.org/project/mmh3/ |
| numpy | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://numpy.org |
| onnxruntime | 1.30.0 | MIT License | https://onnxruntime.ai |
| opentelemetry-api | 1.45.0 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging |
| pillow | 12.3.0 | MIT-CMU | https://python-pillow.github.io |
| portalocker | 3.2.0 | BSD-3-Clause | https://github.com/wolph/portalocker/ |
| prometheus_client | 0.26.0 | Apache-2.0 AND BSD-2-Clause | https://github.com/prometheus/client_python |
| protobuf | 6.33.6 | 3-Clause BSD License | https://developers.google.com/protocol-buffers/ |
| py_rust_stemmers | 0.1.8 | MIT (vérifiée à la main) | https://github.com/qdrant/py-rust-stemmers (fichier LICENSE, API GitHub spdx_id MIT) |
| pydantic | 2.13.5 | MIT | https://github.com/pydantic/pydantic |
| pydantic-settings | 2.15.0 | MIT | https://github.com/pydantic/pydantic-settings |
| pydantic_core | 2.46.5 | MIT | https://github.com/pydantic |
| python-dotenv | 1.2.4 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| PyYAML | 6.0.3 | MIT License | https://pyyaml.org/ |
| qdrant-client | 1.19.1 | Apache Software License | https://github.com/qdrant/qdrant-client |
| requests | 2.34.2 | Apache Software License | https://github.com/psf/requests |
| soupsieve | 2.10 | MIT | https://github.com/facelessuser/soupsieve |
| starlette | 1.7.0 | BSD-3-Clause | https://github.com/Kludex/starlette |
| tokenizers | 0.22.2 | Apache Software License | https://github.com/huggingface/tokenizers |
| tqdm | 4.70.1 | MPL-2.0 AND MIT | https://tqdm.github.io |
| typing-inspection | 0.4.4 | MIT | https://github.com/pydantic/typing-inspection |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| urllib3 | 2.8.0 | MIT | https://github.com/urllib3/urllib3/blob/main/CHANGES.rst |
| uvicorn | 0.54.0 | BSD-3-Clause | https://uvicorn.dev/ |
| uvloop | 0.23.0 | Apache Software License; MIT License | UNKNOWN |
| watchfiles | 1.3.0 | MIT License | https://github.com/samuelcolvin/watchfiles |
| websockets | 17.2 | BSD-3-Clause | https://github.com/python-websockets/websockets |

## Paquets npm de l'interface (8)

| Paquet | Version | Licence | Source |
|---|---|---|---|
| @phosphor-icons/web | 2.1.2 | MIT | git+https://github.com/phosphor-icons/web.git |
| @rive-app/canvas | 2.44.0 | MIT | https://github.com/rive-app/rive-wasm/tree/master/js |
| preact | 11.0.0 | MIT | preactjs/preact |
| workbox-core | 7.4.1 | MIT | git+https://github.com/googlechrome/workbox.git |
| workbox-precaching | 7.4.1 | MIT | git+https://github.com/googlechrome/workbox.git |
| workbox-routing | 7.4.1 | MIT | git+https://github.com/googlechrome/workbox.git |
| workbox-strategies | 7.4.1 | MIT | git+https://github.com/googlechrome/workbox.git |
| workbox-window | 7.4.1 | MIT | git+https://github.com/googlechrome/workbox.git |
