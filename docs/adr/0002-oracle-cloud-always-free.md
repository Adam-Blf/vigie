# ADR 0002. Oracle Cloud Always Free plutôt qu'AWS

- **Statut** : accepté
- **Date** : 2026-10-02
- **Auteurs** : Emilien Morice, Adam Beloucif

## Contexte

La proposition de sujet remise à l'enseignant prévoyait une VM créée par Terraform sur
AWS. Deux faits ont changé la donne au moment de démarrer.

- Le compte AWS d'Adam est resté bloqué en vérification, sans date de déblocage.
- Le plan gratuit AWS ouvert aux nouveaux comptes repose désormais sur des crédits valables
  six mois. Une fois les crédits consommés ou la période écoulée, toute ressource encore
  allumée devient payante. Pour une instance qui doit tourner jusqu'à la soutenance et
  servir de démonstration ensuite, ce n'est pas compatible avec l'ADR 0001.

Oracle Cloud propose une offre **Always Free** sans limite de durée, qui inclut des
instances Arm Ampere A1. En 2026, cette offre est réduite à **2 OCPU et 12 Go de mémoire**
au total. L'authentification OCI est déjà fonctionnelle sur le poste d'Adam, région
d'origine `eu-paris-1`, et le provider Terraform `oracle/oci` en version `~> 7.0` valide une
configuration `VM.Standard.A1.Flex`.

## Décision

Vigie est déployé sur **une seule instance `VM.Standard.A1.Flex` Always Free** (2 OCPU,
12 Go, Ubuntu Arm), dans la région `eu-paris-1`, créée et détruite par Terraform. Le
réseau (VCN, sous-réseau, liste de sécurité limitée à SSH depuis l'IP d'administration,
80 et 443), le bucket Object Storage des sauvegardes et le budget d'alerte sont décrits
dans le même code Terraform.

## Conséquences

- **Images `linux/arm64` obligatoires.** Toutes les images sont construites en
  multi-architecture (`linux/amd64,linux/arm64`) avec QEMU en CI, et les wheels `aarch64`
  de chaque dépendance native sont vérifiées dès la conteneurisation.
- **Budget serré.** 12 Go pour l'OS, k3s, Ollama, Qdrant, MLflow, Prometheus et jusqu'à
  trois pods d'API. Le tableau de budget de `docs/architecture.md` fait foi, et l'image
  de l'API ne contient pas torch.
- **Manque de capacité possible.** Les instances Arm gratuites sont souvent épuisées dans
  une région. La région `eu-paris-1` n'a probablement qu'un domaine de disponibilité, donc
  changer `ad_number` ne sert à rien. La parade est un `terraform apply` relancé toutes les
  10 minutes et journalisé (`python tasks.py infra-retry`), sans jamais passer le compte
  en payant. Après 7 jours sans capacité, le plan B s'applique : cluster k3d local et
  `terraform plan` comme preuve, enseignant prévenu.
- **Récupération des instances inactives.** Oracle peut reprendre une instance Always
  Free jugée inactive ; une charge de fond légère et planifiée l'évite.
- **Écart avec la proposition initiale.** La proposition parlait d'AWS. Le changement de
  fournisseur ne retire aucun niveau de la grille : la VM reste créée par Terraform. Il
  est expliqué dans le rapport.
- **Aucune donnée d'accès dans le dépôt.** OCID, IP d'administration, clé SSH et fichier
  `terraform.tfvars` restent hors de Git. Aucune IP de VM ni aucun OCID n'apparaît dans la
  documentation ou les captures.
