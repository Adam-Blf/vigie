# Vigie et le règlement (UE) 2024/1689 sur l'IA

Analyse faite le 7 octobre 2026 sur le texte publié au Journal officiel (CELEX 32024R1689,
téléchargé depuis Cellar le même jour). Une modification ultérieure du règlement, par
exemple par le paquet « omnibus numérique » proposé par la Commission fin 2025, n'a pas été
vérifiée ici : relire les articles cités avant toute ouverture au-delà du jury.

Vigie est un projet de cours (module MLOps, M2 Data Engineering et IA, EFREI Paris) dont
le sujet a été choisi et rédigé par les deux étudiants, Adam Beloucif et Emilien Morice.
Cette analyse n'est pas un avis juridique.

## Ce qu'est Vigie au sens du règlement

| Question | Réponse | Fondement |
|---|---|---|
| Système d'IA ? | oui : un LLM génère une réponse à partir de passages récupérés | article 3, point 1 |
| Rôle du binôme | **fournisseur** du système Vigie (développé et mis en service sous son nom) et **déployeur** quand il l'exploite pour le jury | article 3, points 3 et 4 |
| Fournisseur d'un modèle d'IA à usage général ? | non : Ministral 3 3B est fourni par Mistral AI, utilisé sans réentraînement ; la quantification Q4_K_M est celle publiée par Ollama | article 3, point 63 ; chapitre V à la charge de Mistral AI |
| Exclusion « recherche et développement » ? | discutable : l'article 2.8 exclut le développement avant mise en service, mais la démonstration au jury avec des jetons nominatifs ressemble à une mise en service limitée. **Choix prudent : Vigie applique les obligations qui le viseraient** | article 2, paragraphe 8 |
| Pratique interdite ? | non : aucune technique manipulatrice, aucune notation sociale, aucune biométrie | article 5 |
| Haut risque ? | non, voir ci-dessous | article 6, annexe III |

### Pourquoi Vigie n'est pas à haut risque

- **Annexe III, point 8 a)** vise les systèmes destinés à être utilisés *par les autorités
  judiciaires ou en leur nom* pour rechercher et interpréter la loi, ou dans un règlement
  extrajudiciaire de litige. La destination de Vigie est une équipe conformité bancaire qui
  cherche un article de règlement : ni autorité judiciaire, ni règlement de litige.
- **Annexe III, point 5 b)** (solvabilité, note de crédit) : Vigie ne traite aucune donnée de
  client et ne produit aucune évaluation de personne.
- **Annexe III, point 4** (emploi) : sans objet.
- Vigie n'est pas un composant de sécurité d'un produit de l'annexe I.

Cette conclusion tient à la **destination** déclarée (aide à la recherche documentaire,
`README.md`, page À propos). Une banque qui s'en servirait pour décider d'un crédit, d'une
embauche ou d'une sanction sortirait de cette destination et devrait refaire l'analyse.

## Obligations qui s'appliquent et leur preuve

Le chapitre I (dont l'article 4) s'applique depuis le 2 février 2025, l'article 50 depuis
le 2 août 2026 (article 113).

| Obligation | Mesure dans Vigie | Où c'est appliqué | Preuve |
|---|---|---|---|
| Art. 50.1 : informer la personne qu'elle interagit avec une IA | bandeau permanent « Vous parlez à une IA… pas un conseil juridique » ; mention sous chaque réponse ; page À propos | `web/src/app/App.tsx:108`, `web/src/chat/AnswerBubble.tsx:85`, clés `banner.ai`, `answer.aiNotice`, `about.ai` de `web/src/i18n/fr.ts` | test Playwright `legal pages carry the mandatory mentions`, `web/e2e/screens.spec.ts:134` |
| Art. 50.2 : sortie marquée dans un format lisible par machine | en-tête `X-AI-Generated: true` sur toute réponse produite par le modèle (`/v1/ask`, `/v1/ask/stream`), champ `model` dans le corps ; une question bloquée, qui reçoit un texte fixe, n'est pas marquée | `src/vigie/api/routes.py:38`, `src/vigie/api/routes.py:75`, `src/vigie/api/routes.py:100` | `tests/test_api_ai_marker.py`, vu rouge : `docs/proofs/J16/ai-marker-red.txt` |
| Art. 50.2, suite : marquage qui survit à la copie | « Copier avec les citations » ajoute la mention « Réponse générée par une IA » au texte copié | `web/src/chat/AnswerBubble.tsx:37` à `web/src/chat/AnswerBubble.tsx:40` | `web/src/chat/chat-logic.test.ts:41` |
| Art. 4 : maîtrise de l'IA des personnes qui l'exploitent | les deux exploitants sont les auteurs, formés par le cours ; les limites sont écrites (`docs/risk-map.md`, `docs/redteam.md`) | documentation | sans objet |

### Bonnes pratiques volontaires

Le règlement n'impose ni journal d'audit ni gestion des risques à un système qui n'est pas
à haut risque. Vigie en tient quand même, sans prétendre à une conformité « haut risque » :

- journal d'audit chaîné par hash (`src/vigie/api/audit.py`), 30 jours ;
- cartographie des risques OWASP LLM (`docs/risk-map.md`) et modèle de menace
  (`docs/threat-model.md`) ;
- évaluation avant promotion et red teaming en CI (`docs/redteam.md`) ;
- citations vérifiées contre le corpus, refus quand aucun texte ne répond.

## Limites

- **Marquage technique.** Il n'existe pas encore de norme harmonisée pour marquer un texte
  généré ; un en-tête HTTP et une mention textuelle sont ce que « la technologie permet »
  pour du texte court, mais un copier-coller manuel de la réponse seule perd la mention.
- **Exclusion de l'article 2.8.** Le choix d'appliquer l'article 50 est prudent, pas une
  qualification juridique tranchée.
- **Modifications du règlement** après le 2 août 2026 non vérifiées, voir l'en-tête.
