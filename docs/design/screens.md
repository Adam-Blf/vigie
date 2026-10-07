# Écrans de l'interface Vigie

Ce document décrit chaque écran avant son code. Tant que la maquette Figma du lot 1 du
designer n'est pas livrée, il fait foi ; ensuite, c'est la maquette qui l'emporte et ce
fichier est mis à jour pour la suivre.

## Principes communs

- **Pile** : Vite, TypeScript strict, Preact. Aucune ressource tierce chargée à
  l'exécution : polices système, icônes Phosphor (graisse `regular` seulement) et runtime
  Rive servis depuis l'application elle-même.
- **Gabarit** : en-tête (logo, navigation, bascule de thème), bandeau de transparence
  permanent, contenu, pied de page avec la source EUR-Lex et la décision 2011/833/UE.
  Un lien d'évitement « Aller au contenu » précède l'en-tête.
- **Bandeau permanent** : « Vous parlez à une IA. Vigie est un outil d'aide à la
  recherche, pas un conseil juridique. Seuls les textes publiés au Journal officiel de
  l'Union européenne font foi. »
- **Thème** : système, clair ou sombre. Un petit script servi en fichier pose
  `data-theme` avant le premier rendu, pour éviter un éclair de la mauvaise couleur.
- **Points de rupture** : 600, 960 et 1 280 px. Aucun défilement horizontal à 360 px.
  Hauteurs en `dvh`, marges `safe-area-inset` sur mobile.
- **Langues** : français par défaut, anglais en option. `<html lang>` suit la langue.
- **Accessibilité** : cibles de 44 px, anneau de focus de 2 px, contrastes AA calculés
  par `python tasks.py contrast`.

## Chat (`/`)

L'écran principal, le seul que la plupart des gens verront.

- **État vide** : la mascotte au repos, une présentation en deux phrases, le rappel « Ne
  saisissez aucune donnée confidentielle ou personnelle », et quatre exemples de
  questions cliquables (DORA, AI Act, RGPD, lutte anti-blanchiment).
- **Fil de messages** : la question à droite, la réponse à gauche. Chaque question est
  traitée seule par l'API ; un texte sous le fil le dit (« l'historique reste sur cet
  appareil et n'est pas envoyé avec la question suivante »).
- **Bulle de réponse** : texte rendu en `textContent` seulement, citations
  `[DORA art. 28 §1]` sous forme de boutons au nom accessible complet, mention « Réponse
  générée par une IA, à vérifier dans le texte officiel », pied « version, modèle, durée »
  pour rendre le canary visible. Actions « Copier avec les citations » et « Voir la
  source ». Si le filtre a retiré une référence, la bulle l'indique.
- **Badge « Bloqué par Vigie »** : icône bouclier et texte, avec une explication courte
  selon le motif (`injection`, `jailbreak`, `prompt_leak`, `pii`, `other`).
- **Refus faute de source** : message neutre, mascotte en état `unknown`.
- **Panneau de citation** : élément `dialog` modal (focus piégé, Échap, retour du focus
  sur le bouton d'origine). Il montre le règlement, l'article, le paragraphe, l'extrait,
  la date du corpus et un lien EUR-Lex (`rel="noopener noreferrer"`). Panneau latéral de
  420 px au-dessus de 960 px, panneau bas pleine largeur en dessous.
- **Saisie** : zone de texte qui grandit, compteur `n / 2 000`, Entrée envoie, Maj+Entrée
  saute une ligne, saisie IME respectée. Bouton « Nouvelle conversation ».
- **Chargement** : mascotte `searching` au moins 600 ms ; après 8 s, « La recherche prend
  plus de temps que prévu » et un bouton Annuler.
- **Erreurs** : 401 ouvre la saisie du jeton ; 413 et 422 s'affichent sous le champ ; 429
  indique le délai `Retry-After` ; 5xx affiche l'identifiant de trace avec un bouton
  Copier ; réseau coupé, mascotte `error`.
- **Mascotte** : `aria-hidden`, doublée d'un texte de statut lu par les lecteurs
  d'écran. La réponse finale seule est annoncée par `aria-live="polite"`.

## Réglages (`/settings`)

- **Jeton d'accès** : champ mot de passe, case « Rester connecté sur cet appareil »
  décochée par défaut (sinon `sessionStorage`), bouton Se déconnecter qui efface jeton et
  historique.
- **Langue** : français ou anglais.
- **Thème** : système, clair, sombre.
- **Installation** : bouton Installer quand le navigateur le permet, sinon un texte qui
  explique pourquoi.
- **Version** : version de l'interface et version de l'API vue dans la dernière réponse.
- **Historique local** : bouton d'effacement.

## Mon usage (`/usage`)

Données de `GET /v1/usage/me` : questions du jour sur le quota quotidien, total, questions
bloquées par Vigie et questions restées sans réponse dans les textes. Barre de progression
avec texte. Sans jeton, renvoi vers les réglages.

## À propos (`/about`)

Ce que fait Vigie, les textes couverts, la mention pédagogique (« Projet réalisé dans le
cadre du cours MLOps, M2 Data Engineering et IA, EFREI Paris. Projet pédagogique, non
affilié officiellement à l'EFREI. »), la transparence de l'article 50 de l'AI Act, et la
version.

## Mentions légales (`/legal`)

Éditeurs (les deux étudiants, responsables conjoints), contact, directeur de
publication, hébergeur. Aucune adresse de domicile, rien au-delà du minimum légal.

## Confidentialité (`/privacy`)

Responsables de traitement, finalités et bases légales, données traitées, durées (audit
30 jours, usage 12 mois, jeton jusqu'à révocation), destinataires, aucun fournisseur de
LLM tiers, droits et saisine de la CNIL, absence de décision automatisée. Aucun cookie ni
mesure d'audience ; stockage technique listé (jeton, préférences, historique local).

## Hors ligne (`/offline` et réseau coupé)

Mascotte `error`, message « Vous êtes hors ligne. Vigie a besoin du réseau pour
interroger les textes. » et bouton Réessayer. Affiché aussi quand le navigateur passe
hors ligne pendant l'usage.

## 404

Mascotte `unknown`, « Cette page n'existe pas », lien vers le chat.

## Erreur serveur (`/error`)

Mascotte `error`, message court, identifiant de trace copiable quand il existe, lien vers
le chat.

## Bandeaux transverses

- **Nouvelle version disponible** : le service worker est en `registerType: 'prompt'`.
  Le bandeau propose de recharger, jamais de rechargement automatique pendant une saisie.
- **Installation** : proposée une seule fois, après la troisième question, discrète et
  refermable.

## Contrat d'API vu par l'interface

Contrat vérifié contre l'API du J5 le 6 octobre 2026 par la suite `npm run e2e:live`.

- `POST /v1/ask/stream`, corps `{ "question": string }` (1 à 2 000 caractères), en-tête
  `Authorization: Bearer <jeton>`, `Accept: text/event-stream`.
- Flux SSE : des événements `delta` (`{"text": "..."}`) portent le texte brut du modèle au
  fil de l'eau, un événement `answer` porte la réponse vérifiée, affichée à la place des
  deltas, un événement `error` porte `{error, trace_id}`. Si le serveur répond en
  `application/json`, la réponse complète est lue d'un bloc.
- Réponse complète : `answer`, `citations[{label, regulation, article, paragraph,
  excerpt, url}]`, `blocked`, `block_reason`, `refused`, `trace_id`, `app_version`,
  `bundle_version`, `model`, `latency_ms`, et en option `citations_removed` (nombre de
  références retirées par le filtre) et `corpus_date`.
- `GET /v1/usage/me` : `requests_today`, `daily_quota`, `requests`, `blocked`, `refused`
  (l'API renvoie aussi `user`, les jetons et le coût, que l'écran n'affiche pas).
- L'URL de base vient de `config.json`, chargé au démarrage, jamais figée au build.

## Mesures

Lighthouse CI (`npm run --prefix web lhci`, profil mobile, médiane de trois runs) le
6 octobre 2026 : accueil à 98 en performance, 100 en accessibilité et 100 en bonnes
pratiques, LCP 1 841 ms, CLS 0,001, TBT 137 ms ; page À propos à 99, 100 et 100, LCP
1 656 ms. Toutes les assertions de `web/lighthouserc.json` passent. Lighthouse 12.6.1,
celui que livre `@lhci/cli` 0.15.1, ne sait pas lire la trace de Chrome 154 (erreur
`NO_NAVSTART`) : on lui donne le Chrome de Playwright par `CHROME_PATH`.

La suite `npm run --prefix web e2e:live` rejoue six parcours contre l'API lancée en local
(`VIGIE_API_PROXY`, `VIGIE_E2E_TOKEN`) : réponse en flux SSE avec article cité, attaque bloquée,
jeton inconnu, question trop longue, écran d'usage, axe sans violation grave. Vue rouge sur l'écran d'usage avant la
correction du contrat, verte après. Pièces dans `docs/proofs/J6/`.
