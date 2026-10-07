// French dictionary, the reference language. Every key here must exist in en.ts,
// which a unit test enforces. French typography wants a no-break space before
// ":", ";", "?" and "!", kept as a literal U+00A0 that the Unicode clean-up must leave alone.

export const fr = {
  "app.name": "Vigie",
  "app.tagline": "Le copilote conformité qui cite ses sources",
  "skip.link": "Aller au contenu",
  "nav.label": "Navigation principale",
  "nav.chat": "Chat",
  "nav.settings": "Réglages",
  "nav.usage": "Mon usage",
  "nav.about": "À propos",
  "theme.toggle": "Thème : {theme}",
  "theme.system": "Système",
  "theme.light": "Clair",
  "theme.dark": "Sombre",
  "banner.ai":
    "Vous parlez à une IA. Vigie est un outil d'aide à la recherche, pas un conseil juridique. Seuls les textes publiés au Journal officiel de l'Union européenne font foi.",
  "footer.source":
    "Textes : EUR-Lex, © Union européenne. Réutilisation autorisée avec mention de la source (décision 2011/833/UE).",
  "footer.legal": "Mentions légales",
  "footer.privacy": "Confidentialité",
  "footer.about": "À propos",
  "footer.label": "Pied de page",
  "demo.banner": "Mode démo : réponses figées, aucune question n'est envoyée au serveur.",

  "chat.title": "Posez votre question réglementaire",
  "chat.intro":
    "Vigie répond aux questions sur DORA, l'AI Act, le RGPD et la lutte anti-blanchiment, en citant l'article exact. Si aucun texte ne répond, elle le dit.",
  "chat.privacy": "Ne saisissez aucune donnée confidentielle ou personnelle.",
  "chat.examples": "Exemples de questions",
  "chat.example.1": "Quels contrats avec des prestataires TIC DORA impose-t-il de documenter ?",
  "chat.example.2": "Quelles obligations de transparence l'AI Act prévoit-il pour un chatbot ?",
  "chat.example.3": "Dans quel délai notifier une violation de données personnelles ?",
  "chat.example.4": "Quels incidents liés aux TIC faut-il déclarer à l'autorité compétente ?",
  "chat.input.label": "Votre question",
  "chat.input.placeholder": "Une question sur DORA, l'AI Act, le RGPD ou l'AMLR",
  "chat.input.hint": "Entrée pour envoyer, Maj+Entrée pour aller à la ligne.",
  "chat.counter": "{count} / {max} caractères",
  "chat.send": "Envoyer",
  "chat.cancel": "Annuler",
  "chat.new": "Nouvelle conversation",
  "chat.history.note":
    "L'historique reste sur cet appareil. Chaque question est traitée seule, sans le contexte des précédentes.",
  "chat.log": "Conversation",
  "chat.you": "Vous",
  "chat.vigie": "Vigie",
  "chat.slow": "La recherche prend plus de temps que prévu.",
  "chat.cancelled": "Question annulée.",
  "chat.empty": "Saisissez une question avant d'envoyer.",

  "answer.aiNotice": "Réponse générée par une IA, à vérifier dans le texte officiel.",
  "answer.copy": "Copier avec les citations",
  "answer.copied": "Réponse copiée.",
  "answer.viewSource": "Voir la source",
  "answer.sources": "Sources",
  "answer.sourcesCopy": "Sources :",
  "answer.meta": "Version {version}, modèle {model}, {duration}",
  "answer.removed.one": "Une référence non vérifiée a été retirée.",
  "answer.removed.many": "{count} références non vérifiées ont été retirées.",
  "answer.unknown": "Aucun article ne répond",
  "answer.streaming": "Vigie rédige la réponse",

  "blocked.badge": "Bloqué par Vigie",
  "blocked.injection": "La question contenait une tentative d'injection d'instructions.",
  "blocked.jailbreak": "La question cherchait à contourner les règles de Vigie.",
  "blocked.prompt_leak": "La question cherchait à obtenir les instructions internes de Vigie.",
  "blocked.pii": "La question contenait des données personnelles. Retirez-les puis réessayez.",
  "blocked.other": "La question a été arrêtée par les garde-fous de Vigie.",

  "citation.open": "Ouvrir la citation {label}",
  "citation.close": "Fermer",
  "citation.regulation": "Texte",
  "citation.article": "Article",
  "citation.paragraph": "Paragraphe",
  "citation.excerpt": "Extrait",
  "citation.eurlex": "Lire sur EUR-Lex",
  "citation.newTab": "(s'ouvre dans un nouvel onglet)",
  "citation.corpusDate": "Corpus du {date}",

  "error.unauthorized": "Jeton absent, expiré ou révoqué. Saisissez un jeton d'accès valide.",
  "error.too_large": "La question dépasse la taille autorisée.",
  "error.invalid": "La question doit contenir entre 1 et {max} caractères.",
  "error.rate_limited": "Trop de questions d'un coup. Réessayez dans {seconds} s.",
  "error.rate_limited.later": "Trop de questions d'un coup. Réessayez dans un instant.",
  "error.server": "Le serveur a rencontré une erreur.",
  "error.network": "Connexion impossible. Vérifiez votre réseau puis réessayez.",
  "error.protocol": "La réponse du serveur est illisible.",
  "error.trace": "Identifiant de trace : {id}",
  "error.copyTrace": "Copier l'identifiant",
  "error.traceCopied": "Identifiant copié.",

  "token.title": "Jeton d'accès",
  "token.label": "Jeton",
  "token.remember": "Rester connecté sur cet appareil",
  "token.rememberHint": "Case décochée, le jeton est oublié à la fermeture de l'onglet.",
  "token.save": "Enregistrer le jeton",
  "token.saved": "Jeton enregistré.",
  "token.logout": "Se déconnecter",
  "token.loggedOut": "Jeton et historique effacés.",
  "token.missing": "Saisissez votre jeton d'accès pour poser une question.",
  "token.goSettings": "Saisir le jeton",

  "settings.title": "Réglages",
  "settings.language": "Langue",
  "settings.theme": "Thème",
  "settings.install": "Installation",
  "settings.install.action": "Installer Vigie",
  "settings.install.done": "Vigie est installée sur cet appareil.",
  "settings.install.unavailable":
    "Votre navigateur ne propose pas l'installation pour le moment. Elle demande une connexion HTTPS et un navigateur compatible.",
  "settings.version": "Version",
  "settings.version.ui": "Interface {version}",
  "settings.version.api": "API {version}, modèle {model}",
  "settings.version.apiUnknown": "Version de l'API connue après la première réponse.",
  "settings.history": "Historique local",
  "settings.history.clear": "Effacer l'historique",
  "settings.history.cleared": "Historique effacé.",
  "lang.fr": "Français",
  "lang.en": "English",

  "usage.title": "Mon usage",
  "usage.today": "Questions aujourd'hui",
  "usage.quota": "{used} sur {quota}",
  "usage.total": "Questions au total",
  "usage.blocked": "Questions bloquées par Vigie",
  "usage.refused": "Questions sans réponse dans les textes",
  "usage.loading": "Chargement de votre usage…",
  "usage.needToken": "Saisissez votre jeton d'accès pour consulter votre usage.",
  "usage.demo": "En mode démo, l'usage affiché est fictif.",

  "about.title": "À propos de Vigie",
  "about.p1":
    "Vigie aide les équipes conformité des banques à appliquer la réglementation européenne. Elle cherche dans DORA, l'AI Act, le RGPD et le règlement anti-blanchiment, puis répond en citant l'article exact.",
  "about.p2":
    "Quand aucun texte ne répond, Vigie le dit au lieu d'inventer. Les tentatives de manipulation sont bloquées avant d'atteindre le modèle de langage.",
  "about.ai.title": "Transparence",
  "about.ai":
    "Vous échangez avec un système d'IA générative (transparence prévue par l'article 50 du règlement (UE) 2024/1689 sur l'IA). Ses réponses sont produites automatiquement, peuvent contenir des erreurs et ne constituent pas un conseil juridique. Le modèle de langage tourne sur notre propre serveur, aucun fournisseur tiers ne reçoit vos questions.",
  "about.school":
    "Projet de cours réalisé dans le cadre du module MLOps, M2 Data Engineering et IA, EFREI Paris. Le sujet a été choisi et rédigé par les deux étudiants eux-mêmes. Projet pédagogique, non affilié officiellement à l'EFREI, qui n'en est ni l'éditeur ni le responsable.",
  "about.sources.title": "Sources",
  "about.sources":
    "© Union européenne, https://eur-lex.europa.eu/, réutilisation autorisée avec mention de la source (décision 2011/833/UE). Textes découpés par article et remis en forme, sans modification de leur contenu. Seule la version publiée au Journal officiel de l'Union européenne fait foi.",

  "legal.title": "Mentions légales",
  "legal.editor.title": "Éditeurs",
  "legal.editor":
    "Adam Beloucif et Emilien Morice, étudiants en M2 Data Engineering et IA à l'EFREI Paris, éditeurs du site à titre non professionnel.",
  "legal.director.title": "Directeurs de la publication",
  "legal.director": "Adam Beloucif et Emilien Morice.",
  "legal.contact.title": "Contact",
  "legal.contact": "adam.beloucif@efrei.net, emilien.morice@efrei.net",
  "legal.host.title": "Hébergeur",
  "legal.host":
    "Oracle France SAS, 15 boulevard Charles de Gaulle, 92715 Colombes Cedex, France, téléphone +33 1 57 60 83 02. Service Oracle Cloud Infrastructure, offre Always Free, région Paris.",
  "legal.ip.title": "Propriété intellectuelle",
  "legal.ip":
    "Code et interface de Vigie : © 2026 Adam Beloucif et Emilien Morice, tous droits réservés. Textes réglementaires : EUR-Lex, © Union européenne, réutilisation autorisée avec mention de la source (décision 2011/833/UE). Composants tiers et leurs licences : /third-party-licenses.txt.",

  "privacy.title": "Confidentialité",
  "privacy.controllers.title": "Responsables du traitement",
  "privacy.controllers":
    "Adam Beloucif et Emilien Morice, responsables conjoints du traitement au sens de l'article 26 du RGPD. Vous pouvez exercer vos droits auprès de l'un ou de l'autre, aux adresses des mentions légales.",
  "privacy.purposes.title": "Finalités et bases légales",
  "privacy.purposes":
    "Répondre à vos questions et appliquer le quota de votre jeton (exécution du service demandé, article 6.1.b du RGPD). Tenir un journal d'audit et protéger le service contre les abus (intérêt légitime à sécuriser le service et à retracer ses réponses, article 6.1.f).",
  "privacy.data.title": "Données traitées",
  "privacy.data":
    "Le nom ou pseudonyme associé à votre jeton, l'empreinte du jeton (jamais le jeton lui-même), le texte de vos questions et des réponses, les horodatages et des compteurs d'usage. Le journal d'audit ne contient ni adresse IP ni empreinte de navigateur, et les données personnelles évidentes (e-mail, IBAN, carte, téléphone) y sont masquées avant écriture. Ces données sont nécessaires pour utiliser le service.",
  "privacy.retention.title": "Durées de conservation",
  "privacy.retention":
    "Journal d'audit : 30 jours. Compteurs d'usage : 12 mois. Empreinte du jeton : jusqu'à sa révocation ou son expiration, puis 12 mois.",
  "privacy.recipients.title": "Destinataires",
  "privacy.recipients":
    "Les deux responsables, et Oracle comme hébergeur, en région Paris (France). Aucun fournisseur de modèle de langage tiers : le modèle tourne sur notre serveur. Aucun transfert hors de l'Union européenne n'est organisé.",
  "privacy.storage.title": "Stockage sur votre appareil",
  "privacy.storage":
    "Aucun cookie ni outil de mesure d'audience. Seul un stockage technique strictement nécessaire est utilisé : le jeton (pour l'onglet, ou sur l'appareil si vous cochez « Rester connecté »), vos préférences de langue et de thème, et l'historique affiché.",
  "privacy.rights.title": "Vos droits",
  "privacy.rights":
    "Vous pouvez demander l'accès à vos données, leur rectification, leur effacement, la limitation du traitement ou leur portabilité, et vous opposer au traitement fondé sur l'intérêt légitime, en écrivant aux contacts des mentions légales. Réponse sous un mois. Vous pouvez aussi saisir la CNIL (cnil.fr). Aucune décision automatisée ne produit d'effet juridique à votre égard.",

  "offline.title": "Vous êtes hors ligne",
  "offline.body":
    "Vigie a besoin du réseau pour interroger les textes. Votre historique reviendra avec la connexion.",
  "offline.retry": "Réessayer",
  "notFound.title": "Cette page n'existe pas",
  "notFound.body": "Le lien est peut-être ancien. La vigie n'a rien repéré à cette adresse.",
  "notFound.back": "Retour au chat",
  "serverError.title": "Le serveur ne répond pas comme prévu",
  "serverError.body": "Réessayez dans quelques instants. Si le problème persiste, transmettez l'identifiant de trace.",

  "pwa.update": "Une nouvelle version de Vigie est disponible.",
  "pwa.reload": "Mettre à jour",
  "pwa.later": "Plus tard",
  "pwa.install": "Installez Vigie pour l'ouvrir comme une application.",
  "pwa.installAction": "Installer",
  "pwa.dismiss": "Fermer",

  "mascot.idle": "Vigie est prête.",
  "mascot.listening": "Vigie vous écoute.",
  "mascot.searching": "Vigie cherche dans les textes.",
  "mascot.found": "Vigie a trouvé des sources.",
  "mascot.unknown": "Vigie n'a trouvé aucune source.",
  "mascot.blocked": "Vigie a bloqué la question.",
  "mascot.error": "Vigie rencontre un problème.",
} as const;

export type MessageKey = keyof typeof fr;
export type Dictionary = Record<MessageKey, string>;
