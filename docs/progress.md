# Progression

Une ligne par jalon fusionné. Reprise après interruption : repartir du premier jalon qui
n'est pas `DONE`. Statuts possibles : `DONE`, `PARTIEL`, `BLOQUÉ`.

| Date | Jalon | Statut | Preuve | Motif | Suite |
|---|---|---|---|---|---|
| 2026-10-02 | J0 outillage | DONE | `docs/proofs/J0/` (check vert, co-auteurs) | | cadrage en cours sur `docs/framing` |
| 2026-10-02 | J0 cadrage | DONE | `docs/proofs/J0-cadrage/` (check vert, typo vert et vu rouge, mypy tests) | | jalons de construction à partir du corpus |
| 2026-10-02 | J1 corpus | DONE | `docs/proofs/J1/` (ingestion réelle, verrou vu rouge sur l'empreinte et le nombre d'articles, couverture) | | indexation hybride dans Qdrant |
| 2026-10-02 | J3 LLM et RAG | DONE | `docs/proofs/J3/` (trois réponses réelles de Ministral 3B, citation inventée retirée, couverture 99 %) | | brancher la recherche Qdrant à la place des passages fixes ; seuil de latence mesuré sur la VM au J7 et au J14 |
| 2026-10-02 | J8 jeu de référence | DONE | `docs/proofs/J8/` (80 questions vérifiées contre Cellar, partie test scellée, validateur vert puis vu rouge sur brouillons et copie dégradée) | | mesure réelle contre les seuils de `eval/thresholds.yaml` au J11, quand l'API répond de bout en bout |
| 2026-10-06 | J4 benchmark des garde-fous | DONE | `docs/proofs/J4/bench/` (six garde-fous sur le jeu maison `test` et le contrôle deepset, suivi MLflow) | quota gratuit Lakera épuisé sur deepset, 20 exemples sur 116 mesurés pour cet outil | chaîne de garde-fous de production sur `feat/guard` ; latences à refaire sur la VM |
| 2026-10-06 | J9 détection de drift | DONE | `docs/proofs/J9/` (aucune alerte sur 30 questions DORA, trois alertes après 30 questions hors sujet, tests d'intégration avec le vrai MiniLM) | marge du test KS mince sur le lot DORA (p 0,088 pour un seuil de 0,01), documentée dans `docs/drift.md` | exposer `GET /v1/admin/drift` avec l'API au J5 |
| 2026-10-06 | J11 test de charge | PARTIEL | `docs/proofs/J11/` (garde-fous de charge vus rouges, verdict vu rouge, 20 utilisateurs pendant 60 s contre un bouchon local) | mesure réelle impossible tant que l'API du J5 n'est pas fusionnée ; les latences du bouchon ne disent rien de Vigie | lancer `python tasks.py load-local` contre l'API locale dès le J5 et juger contre la section `load` de `eval/thresholds.yaml` |
| 2026-10-06 | J10 red teaming | PARTIEL | `docs/proofs/J10/` (360 attaques générées en local, barrière verte sur un bouchon protégé, vue rouge sur un bouchon qui fuit et sur un jeton faux) | rejeu contre la vraie API impossible tant que le J5 n'est pas fusionné | rejouer en CI contre l'API avec le faux LLM, puis à la main contre Ministral, dès le J5 |
| 2026-10-06 | J12 quantization | DONE | `docs/proofs/J12/` (seuil écrit avant mesure, parité ONNX contre PyTorch 7,5e-8, embedding int8 retenu sur `dev` : taille x 0,25, rappel@5 0,468 puis 0,511, barrière vue rouge sur un seuil dégradé ; Ministral Q4_K_M contre Q8_0 sur CPU, Q4_K_M gardé) | | premier token mesuré à 60 s sur le poste : à mesurer sur la VM au J14 contre le seuil de 5 s ; six réponses sur dix sans citation dans les deux variantes, à reprendre avec la recherche hybride du J2 |

## Décisions par défaut appliquées (section 10 du brief)

| # | Décision | Valeur retenue | Origine |
|---|---|---|---|
| 4 | Visibilité du dépôt | public depuis le 2026-10-06 (historique scanné par gitleaks, aucun secret, OCID ni IP), fusion par PR uniquement, `main` protégée | Adam, 2026-10-06 |
| 12 | Publication avec le nom de l'école | dépôt public, accord de l'enseignant obtenu, mention « projet de cours, sujet rédigé par le binôme » | Adam, 2026-10-06 |
| 14 | Clé Lakera | fournie par Adam, stockée hors dépôt | Adam, 2026-10-02 |

## Reste à faire

Suivi détaillé jalon par jalon dans le tableau ci-dessus. Les points en attente d'une
décision d'Adam sont listés dans la section 10 du brief.
