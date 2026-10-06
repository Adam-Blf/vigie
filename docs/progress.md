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

## Décisions par défaut appliquées (section 10 du brief)

| # | Décision | Valeur retenue | Origine |
|---|---|---|---|
| 4 | Visibilité du dépôt | public depuis le 2026-10-06 (historique scanné par gitleaks, aucun secret, OCID ni IP), fusion par PR uniquement, `main` protégée | Adam, 2026-10-06 |
| 12 | Publication avec le nom de l'école | dépôt public, accord de l'enseignant obtenu, mention « projet de cours, sujet rédigé par le binôme » | Adam, 2026-10-06 |
| 14 | Clé Lakera | fournie par Adam, stockée hors dépôt | Adam, 2026-10-02 |

## Reste à faire

Suivi détaillé jalon par jalon dans le tableau ci-dessus. Les points en attente d'une
décision d'Adam sont listés dans la section 10 du brief.
