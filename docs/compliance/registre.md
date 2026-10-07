# Registre des traitements (RGPD, article 30)

Vigie est un projet de cours : le module MLOps du M2 Data Engineering et IA de l'EFREI
Paris, dont le sujet a été choisi et rédigé par les deux étudiants eux-mêmes, Adam Beloucif
et Emilien Morice. L'EFREI n'est ni responsable du traitement ni éditeur du service.

Les organismes de moins de 250 personnes sont dispensés de registre sauf traitement non
occasionnel (article 30.5) ; Vigie le tient quand même, parce qu'il sert de preuve. Chaque
affirmation renvoie au code ou à la configuration qui l'applique (`fichier:ligne`, état du
commit de ce jalon). Ce qui n'est appliqué par aucun code est écrit comme une limite.

L'agent qui a rédigé ce registre n'est pas avocat. Avant toute ouverture à un public
au-delà du jury, Adam valide avec un professionnel du droit.

## Responsables du traitement

| Rôle | Identité | Contact |
|---|---|---|
| Responsables conjoints (article 26) | Adam Beloucif et Emilien Morice, étudiants, à titre non professionnel | adam.beloucif@efrei.net, emilien.morice@efrei.net |
| Délégué à la protection des données | aucun, non obligatoire (article 37) | |
| Sous-traitant d'hébergement (article 28) | Oracle (Oracle Cloud Infrastructure, région Paris, offre Always Free) | conditions et DPA d'Oracle acceptés à l'ouverture du compte |

L'accord de responsabilité conjointe est rédigé dans
[`accord-responsabilite-conjointe.md`](accord-responsabilite-conjointe.md). **Limite** : il
n'est pas encore signé par les deux étudiants.

## Traitement T1, réponse aux questions

| Rubrique | Contenu | Où c'est appliqué |
|---|---|---|
| Finalité | répondre à une question réglementaire avec des citations, appliquer le quota du jeton | `src/vigie/api/routes.py:64` à `src/vigie/api/routes.py:75` |
| Base légale | exécution du service demandé (6.1.b) | page Confidentialité, `web/src/i18n/fr.ts` clé `privacy.purposes` |
| Personnes concernées | détenteurs d'un jeton : le binôme, l'enseignant, le jury | jetons créés à la main, `src/vigie/api/tokens.py:25` |
| Données | nom ou pseudonyme saisi à la création du jeton, empreinte SHA-256 du jeton, texte de la question | `src/vigie/api/auth.py:28` à `src/vigie/api/auth.py:37`, `src/vigie/api/auth.py:45` |
| Minimisation | question limitée à 2 000 caractères, corps à 16 Ko, aucune IP ni User-Agent conservés, chaque question traitée seule sans historique serveur | `src/vigie/config.py:118`, `src/vigie/config.py:119`, `src/vigie/api/service.py:105` à `src/vigie/api/service.py:127` |
| Destinataires | le binôme ; Oracle comme hébergeur ; **aucun fournisseur de LLM tiers** | fournisseur `ollama` fixé par la configuration de production, `deploy/k8s/base/config/bundle.env:4`, jamais par une requête (test F3.5 du modèle de menace) |
| Transfert hors UE | aucun organisé, VM en région Paris | `infra/terraform` (région du fournisseur) |
| Durée | le temps de la requête pour la question ; l'empreinte du jeton jusqu'à révocation ou expiration (30 jours), puis 12 mois | `src/vigie/config.py:108`, purge `src/vigie/api/auth.py:91` à `src/vigie/api/auth.py:98`, déclenchée chaque jour `src/vigie/api/auth.py:126` à `src/vigie/api/auth.py:131` |

**Limite.** Le fournisseur `mistral` existe dans le code (`src/vigie/config.py:19`,
`src/vigie/config.py:79` à `src/vigie/config.py:81`) pour des mesures sur le poste. Il
enverrait la question à Mistral AI. Aucun manifeste de déploiement ne le sélectionne ; s'il
l'était un jour, cette ligne du registre et la page Confidentialité devraient changer avant.

## Traitement T2, journal d'audit

| Rubrique | Contenu | Où c'est appliqué |
|---|---|---|
| Finalité | retracer chaque réponse (traçabilité AI Act, bonne pratique volontaire) et enquêter sur un abus | `src/vigie/api/service.py:105` |
| Base légale | intérêt légitime (6.1.f) : sécuriser le service et pouvoir expliquer une réponse | page Confidentialité |
| Données | identifiant de trace, nom du détenteur, statut, question et réponse **avec les e-mails, IBAN, cartes et téléphones masqués**, citations, décision des garde-fous, versions | `src/vigie/api/service.py:106` à `src/vigie/api/service.py:126`, masque `src/vigie/guard/pii.py:49`, sortie `src/vigie/guard/output.py:38` |
| Exclusions | ni IP, ni User-Agent, ni jeton | aucun de ces champs n'est écrit, `src/vigie/api/service.py:106` à `src/vigie/api/service.py:126` |
| Intégrité | chaînage par hash, un fichier par pod | `src/vigie/api/audit.py:87` à `src/vigie/api/audit.py:88`, vérification `python -m vigie.api.audit_cli verify` |
| Durée | 30 jours, purge au premier écrit de chaque jour | `src/vigie/config.py:110`, `src/vigie/api/audit.py:82` à `src/vigie/api/audit.py:86`, `src/vigie/api/audit.py:99` à `src/vigie/api/audit.py:110` |
| Accès | les deux responsables, sur la VM | volume de l'API, jamais exposé |

**Limites.** Les noms et adresses postales ne sont pas reconnus par les motifs du masque
(`src/vigie/guard/pii.py:1` à `src/vigie/guard/pii.py:7`) : une personne qui en colle un dans
sa question le retrouve dans le journal pendant 30 jours. Le bandeau « Ne saisissez aucune
donnée confidentielle ou personnelle » (`web/src/i18n/fr.ts`, clé `chat.privacy`) est la
mesure, pas une garantie. La purge des sauvegardes éventuelles du volume n'est pas
automatisée : aucune sauvegarde n'est configurée à ce jour.

## Traitement T3, compteurs d'usage

| Rubrique | Contenu | Où c'est appliqué |
|---|---|---|
| Finalité | quota quotidien par jeton, page « Mon usage », suivi demandé par la grille du cours | `src/vigie/api/usage.py:1` à `src/vigie/api/usage.py:6` |
| Base légale | exécution du service (6.1.b) | page Confidentialité |
| Données | nom du détenteur, identifiant du jeton, horodatage, statut, latence, jetons du modèle, coût estimé, bloqué ou refusé ; **jamais le texte de la question** | schéma `src/vigie/api/usage.py:54` à `src/vigie/api/usage.py:71` |
| Durée | 12 mois, purge à la première écriture de chaque jour | `src/vigie/config.py:113`, `src/vigie/api/usage.py:86` à `src/vigie/api/usage.py:100` |

## Traitement T4, journaux techniques

| Source | Contenu | Durée | Où c'est appliqué |
|---|---|---|---|
| Journaux applicatifs de l'API | événements techniques ; en-tête `Authorization`, jetons, `question` et `answer` retirés avant tout gestionnaire | rotation du moteur de conteneurs | `src/vigie/api/redaction.py:15` à `src/vigie/api/redaction.py:40` |
| Journal d'accès nginx | date, ligne de requête (chemin, jamais le corps), statut, taille, durée ; **sans adresse IP** | rotation du moteur de conteneurs | `deploy/docker/nginx/nginx.conf:26` à `deploy/docker/nginx/nginx.conf:27` |
| Traefik | adresse IP lue en mémoire pour la limite de débit ; journal d'accès non activé | non conservée | `deploy/k8s/base/ingress.yaml:49` |

**Limite.** Le brief vise 7 jours pour les journaux d'accès ; la durée réelle dépend de la
rotation par taille du moteur de conteneurs (k3s), non configurée par le dépôt. Comme ces
journaux ne contiennent ni IP ni question ni jeton, ils ne sont pas traités ici comme des
données personnelles ; à revoir si un champ identifiant y est ajouté.

## Stockage sur l'appareil de l'utilisateur

Aucun cookie, aucun outil de mesure d'audience. Le jeton vit dans `sessionStorage`, ou dans
`localStorage` seulement si la case « Rester connecté » est cochée (`web/src/lib/token.ts:1`
à `web/src/lib/token.ts:2`, `web/src/lib/storage.ts:8`) ; l'historique affiché vit dans
`sessionStorage` (`web/src/chat/turns.ts:28`, `web/src/chat/turns.ts:50`). Ces stockages
sont strictement nécessaires au service demandé (article 82 de la loi Informatique et
Libertés), donc sans bandeau de consentement.

## Droits des personnes

Accès, rectification, effacement, limitation, portabilité (T1 et T3) et opposition (T2),
par courriel aux deux responsables, réponse sous un mois (article 12.3). Exercice manuel :
`python -m vigie.api.tokens list` retrouve les jetons d'une personne, `revoke` les coupe,
les lignes d'usage se filtrent par `user` dans SQLite et les lignes d'audit par `user` dans
les JSONL. **Limite** : aucune commande n'efface encore les lignes d'une seule personne ;
l'effacement ciblé se fait à la main, puis le chaînage d'audit est vérifié de nouveau.

Aucune décision fondée exclusivement sur un traitement automatisé ne produit d'effet
juridique (article 22) : Vigie répond à une question, il ne décide rien sur la personne.

## Analyse d'impact

Pas d'AIPD obligatoire : aucun critère de la liste de la CNIL n'est rempli à deux reprises
(pas de données sensibles attendues, pas de personnes vulnérables, pas de profilage, pas de
grande échelle, pas de croisement de fichiers). Le risque principal, une donnée personnelle
collée dans une question, est traité par le masque, la durée de 30 jours et le bandeau.

## Violations de données

Procédure dans `docs/runbook-incident.md` quand il existera (jalon J17) : révoquer les
jetons, couper par `VIGIE_MAINTENANCE=true`, puis notifier la CNIL sous 72 heures si la
violation présente un risque (article 33). **Limite** : le runbook n'est pas encore écrit.
