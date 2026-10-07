# Sécurité et conformité avant déploiement (J16)

Vigie est un projet de cours, module MLOps du M2 Data Engineering et IA de l'EFREI Paris,
dont le sujet a été choisi et rédigé par ses deux auteurs, Adam Beloucif et Emilien Morice.
Ce document est la preuve du jalon J16 : la checklist de sécurité avant déploiement cochée,
puis le rapport d'audit juridique et ce qui a été corrigé. Les sorties brutes sont dans
[`proofs/J16/`](proofs/J16/), décrites par leur `manifest.json`.

Les documents de conformité détaillés :

- [`compliance/registre.md`](compliance/registre.md), registre des traitements RGPD,
  minimisation et durées, chaque point relié au code qui l'applique ;
- [`compliance/ai-act.md`](compliance/ai-act.md), classement au regard du règlement sur
  l'IA et obligations de transparence ;
- [`compliance/fiches-modeles-donnees.md`](compliance/fiches-modeles-donnees.md), fiches des
  modèles et des jeux de données, licences comprises ;
- [`../THIRD_PARTY_LICENSES.md`](../THIRD_PARTY_LICENSES.md), inventaire généré et vérifié
  en CI ;
- [`compliance/accord-responsabilite-conjointe.md`](compliance/accord-responsabilite-conjointe.md),
  projet d'accord de l'article 26.

## Checklist avant déploiement

État au 7 octobre 2026, sur le commit de ce jalon et sur les images publiées de `main`
(`eddd0e0`). Une case non cochée est une limite, pas un oubli : elle est expliquée.

### Secrets

- [x] Aucun secret dans l'historique : `gitleaks git` sur toutes les branches locales,
  `proofs/J16/gitleaks-history.txt` ; gitleaks bloque aussi en pre-commit et en CI (job
  `secrets` de `.github/workflows/ci.yml`).
- [x] `.env` et `terraform.tfvars` ignorés, secrets lus par variables d'environnement
  (`src/vigie/config.py:25`).
- [x] Jetons `vig_` aléatoires de 32 octets, stockés hachés en SHA-256, comparés à temps
  constant (`src/vigie/api/auth.py:45`, `src/vigie/api/auth.py:141`) ; jamais dans les
  journaux (`src/vigie/api/redaction.py:15` à `src/vigie/api/redaction.py:22`).
- [x] Le build de l'interface ne contient aucun secret : seule l'URL de base est lue au
  démarrage dans `config.json`.

### Authentification et accès

- [x] Chaque route `/v1` vérifie le jeton côté serveur, 401 identique pour absent, inconnu,
  expiré ou révoqué ; 403 pour un jeton `user` sur `/v1/admin` (`docs/api.md`, tests
  `tests/test_api_auth.py`).
- [x] Révocation effective immédiatement, expiration à 30 jours (`src/vigie/config.py:108`).
- [x] Limite par minute et quota quotidien par jeton, limite par IP dans Traefik
  (`deploy/k8s/base/ingress.yaml:49`).

### Entrées et sorties

- [x] Corps à 16 Ko, question à 2 000 caractères, validation Pydantic côté serveur,
  `extra="forbid"` (`src/vigie/api/schemas.py:22`).
- [x] Aucune concaténation SQL : requêtes paramétrées SQLite partout.
- [x] Réponse du LLM rendue en `textContent`, Trusted Types exigés par la CSP, liens
  EUR-Lex construits côté serveur (`docs/threat-model.md`, F2.1 et F2.2).
- [x] Jamais de trace d'exécution renvoyée au client : `{"error", "trace_id"}` seulement.

### Réseau et en-têtes

- [x] CSP, `nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, COOP servis
  par nginx sur toutes les routes : `proofs/J16/headers-web.txt`, relevé sur l'image
  publiée (`deploy/docker/nginx/security-headers.conf:4` à
  `deploy/docker/nginx/security-headers.conf:8`).
- [x] Interface et API sous la même origine, donc pas de CORS en production ; en local,
  CORS limité à l'interface (`src/vigie/config.py:105`).
- [ ] **HTTPS et HSTS en production** : prévus par Traefik et Let's Encrypt
  (`deploy/k8s/README.md`), non vérifiables tant que la VM Oracle n'existe pas (J14
  `BLOQUÉ`). À relever avec `curl -I` dès le premier déploiement.
- [x] `/.well-known/security.txt` (RFC 9116) servi par l'interface, avec `SECURITY.md`.

### Dépendances et images

- [x] `pip-audit` : aucune vulnérabilité connue, sur l'environnement d'exécution et sur
  celui de la CI (`proofs/J16/pip-audit.txt`).
- [x] `npm audit --omit=dev` : 0 vulnérabilité dans ce qui est livré
  (`proofs/J16/npm-audit.txt`). L'outillage de développement (Lighthouse CI) porte 6 avis
  hauts sans correctif publié : jamais livré, rapporté en CI sans bloquer.
- [x] Trivy, CRITICAL et HIGH corrigeables : 0 sur `vigie-api` et `vigie-web`
  (`proofs/J16/trivy-api.txt`, `proofs/J16/trivy-web.txt`) ; Trivy bloque aussi toute
  publication (`.github/workflows/build.yml`).
- [x] Actions épinglées par SHA, Dependabot, verrous `uv.lock` et `package-lock.json`, SBOM
  CycloneDX et signature cosign des images.
- [x] Licences : aucun copyleft fort livré, inventaire régénéré et comparé en CI (job
  `licenses`), politique npm vue rouge (`proofs/J16/web-licences-red.txt`).

### Exploitation

- [x] Journal d'audit purgé à 30 jours, compteurs d'usage et jetons morts à 12 mois, purge
  vue rouge (`proofs/J16/retention-red.txt`).
- [ ] **Sauvegarde et restauration** : aucune sauvegarde du volume configurée. Pour un
  service de démonstration, la perte du volume coûte des compteurs et 30 jours d'audit ;
  le choix est assumé et écrit.
- [ ] **Validation des risques résiduels** du modèle de menace par Adam (décision 15 du
  brief) : en attente, voir la section « Risques résiduels » de `threat-model.md`.

## Audit juridique

Audit mené le 7 octobre 2026 selon la grille de l'agent `legal-advisor` : relecture des
pages Mentions légales, Confidentialité et À propos, de `LICENSE`, `NOTICE`, `SECURITY.md`,
`docs/api.md` et du code qui traite des données. Principe appliqué : afficher le strict
minimum légal, et ne rien promettre que le code n'applique pas. L'agent n'est pas avocat.

| # | Constat | Exposition | Correction |
|---|---|---|---|
| 1 | Mentions légales sans identité, adresse ni téléphone de l'hébergeur | LCEN, article 6 | Oracle France SAS, adresse du siège et téléphone de la page contact d'Oracle France, clé `legal.host` |
| 2 | « Compteurs d'usage : 12 mois » affiché, aucune purge dans le code | promesse non tenue, RGPD 5.1.e | purge quotidienne, `src/vigie/api/usage.py:86` à `src/vigie/api/usage.py:100`, tests vus rouges |
| 3 | « Jeton : jusqu'à sa révocation », l'empreinte restait indéfiniment | idem | purge des jetons morts depuis 12 mois, `src/vigie/api/auth.py:91` à `src/vigie/api/auth.py:98` |
| 4 | Page Confidentialité muette sur le nom du détenteur et sur le texte des réponses | RGPD 13.1 | liste complète, clé `privacy.data` |
| 5 | Droits incomplets : ni opposition, ni limitation, ni portabilité, ni délai | RGPD 13.2.b, 12.3 | clé `privacy.rights` |
| 6 | Responsables conjoints sans accord ni point de contact | RGPD 26 | projet d'accord, exercice des droits auprès de l'un ou l'autre (clé `privacy.controllers`) |
| 7 | « Textes non altérés » alors que `NOTICE` décrit une remise en forme | décision 2011/833/UE, article 6.2.b | « découpés par article et remis en forme, sans modification de leur contenu » |
| 8 | « Système d'IA générative, conformément à l'article 50 » : formule qui suggère une conformité certifiée | pratique trompeuse | information factuelle, réponses automatiques, erreurs possibles |
| 9 | Aucune sortie marquée lisible par machine | AI Act 50.2 | en-tête `X-AI-Generated`, `src/vigie/api/routes.py:38` |
| 10 | Bundle web servi sans les mentions MIT de Preact, Workbox, Phosphor, Rive | licences MIT | `/third-party-licenses.txt` produit au build, politique bloquante |
| 11 | Projet de cours non dit sur l'interface comme écrit par les étudiants | confusion sur l'éditeur | clé `about.school` |
| 12 | Pas de `/.well-known/security.txt` | brief 11.10 | `web/public/.well-known/security.txt` |

### Restent ouverts

- **Entité contractante d'Oracle.** L'identité affichée est celle d'Oracle France SAS
  (siège, SIREN 335 092 318 au répertoire SIRENE). Le contrat Always Free peut désigner une
  autre entité du groupe : Adam la vérifie dans la console Oracle avant la mise en ligne.
- **Accord de l'article 26** à signer par les deux étudiants.
- **Noms et adresses postales** non masqués dans le journal d'audit (limite du masque par
  motifs, `src/vigie/guard/pii.py:1` à `src/vigie/guard/pii.py:7`).
- **Fournisseur `mistral`** présent dans le code pour les mesures sur le poste : jamais
  sélectionné en production (`deploy/k8s/base/config/bundle.env:4`) ; le sélectionner
  imposerait de modifier d'abord la page Confidentialité.
- **Antériorité du nom « Vigie »** (décision 2 du brief) : non vérifiée par ce jalon ; le
  nom reste celui d'un projet de cours, sans dépôt de marque.
