# Infrastructure Oracle Cloud (Always Free)

Ce dossier décrit le nœud unique qui héberge Vigie en production : une VM Ampere
`VM.Standard.A1.Flex` (2 OCPU, 12 Go, Ubuntu 24.04) dans la région `eu-paris-1`, avec
k3s installé au premier démarrage. Tout reste dans l'offre Always Free : coût visé et
surveillé, 0 euro.

## Ce que crée Terraform

| Fichier | Ressources |
|---|---|
| `network.tf` | VCN `10.10.0.0/16`, passerelle Internet, table de routage, liste de sécurité, sous-réseau public `10.10.1.0/24` |
| `main.tf` | instance A1 avec disque de 50 Go, IP publique, clé SSH, cloud-init, IMDS v1 désactivé |
| `budget.tf` | budget mensuel de 1 avec alerte e-mail à 1 % de dépense réelle |
| `storage.tf` | bucket privé `vigie-backups` (sauvegardes Qdrant et MLflow), purge automatique à 30 jours |
| `cloud-init.sh` | pare-feu hôte, durcissement SSH, mises à jour automatiques, fail2ban, charge de fond, k3s épinglé |

Chaque ressource porte les étiquettes libres `Project=vigie` et `Course=MLOps`.

### Ouvertures réseau

| Port | Source | Usage |
|---|---|---|
| 22 | `admin_cidr` uniquement | SSH par clé |
| 80 | Internet | défi ACME et redirection vers HTTPS |
| 443 | Internet | interface et API |
| 6443 | jamais ouvert | API Kubernetes, accessible seulement par tunnel SSH |

L'image Ubuntu d'Oracle bloque tout sauf SSH dans son propre iptables. `cloud-init.sh`
ouvre donc 80 et 443 à ce niveau aussi, ainsi que les plages internes de k3s
(`10.42.0.0/16` pour les pods, `10.43.0.0/16` pour les services), puis enregistre les
règles avec `netfilter-persistent save` avant le démarrage de k3s.

### Durcissement de la VM

- SSH par clé uniquement : `PasswordAuthentication no`, `PermitRootLogin no`, trois
  essais au plus par connexion.
- `unattended-upgrades` actif, fail2ban sur SSH (5 échecs en 10 minutes, bannissement
  d'une heure).
- k3s en version épinglée (`k3s_version`, par défaut `v1.36.5+k3s1`), installé depuis le
  script du même tag, avec `--write-kubeconfig-mode 600` et `--secrets-encryption`.
- Points de terminaison de métadonnées v1 désactivés : une faille SSRF dans un pod ne
  peut plus lire les métadonnées de l'instance avec une simple requête GET.
- Aucun secret dans `user_data`, qui reste lisible depuis la VM. La seule variable
  injectée est la version de k3s.

### Charge de fond contre la récupération des instances inactives

Oracle peut récupérer une instance Always Free dont le 95e centile d'utilisation CPU
reste sous 20 % pendant sept jours. Le minuteur systemd `vigie-keepalive.timer` fait
tourner un cœur pendant 8 minutes chaque heure, avec la priorité la plus basse
(`Nice=19`, `CPUWeight=1`), ce qui maintient ce centile au-dessus du seuil sans jamais
gêner la charge réelle. Pour le vérifier ou le couper :

```sh
systemctl list-timers vigie-keepalive.timer
sudo systemctl disable --now vigie-keepalive.timer
```

## Première configuration

Prérequis : Terraform 1.9 ou plus récent, `~/.oci/config` fonctionnel (profil `DEFAULT`),
clé `~/.ssh/vigie_deploy`.

1. Copier les variables, hors Git :

   ```sh
   cp ~/.oci/vigie.tfvars infra/terraform/terraform.tfvars
   git status --ignored infra/terraform   # terraform.tfvars doit apparaître comme ignoré
   ```

   Si l'IP publique a changé, mettre à jour `admin_cidr` avec la sortie de
   `curl -4 -s ifconfig.me`, suivie de `/32`.

2. Initialiser avec l'état **hors du dépôt**. Le bloc `backend "local" {}` est vide
   exprès : sans `-backend-config`, Terraform refuserait de deviner un chemin.

   ```sh
   cd infra/terraform
   terraform init -backend-config="path=C:/Users/adamb/.vigie/terraform/terraform.tfstate"
   ```

3. Vérifier puis appliquer :

   ```sh
   terraform fmt -check && terraform validate
   terraform plan -out=C:/Users/adamb/.vigie/terraform/vigie.tfplan
   terraform apply C:/Users/adamb/.vigie/terraform/vigie.tfplan
   ```

Sous Windows, exporter `OCI_CLI_SUPPRESS_FILE_PERMISSIONS_WARNING=True` et
`SUPPRESS_LABEL_WARNING=True` : les droits des clés sont déjà restreints par `icacls`.

L'état Terraform, les plans et les journaux vivent dans `~/.vigie/terraform/`. Ils ne
sont jamais commités (`*.tfstate*` et `terraform.tfvars` sont dans `.gitignore`). Le
fichier `.terraform.lock.hcl`, lui, est versionné pour figer le provider `oracle/oci`.

## Session type

```sh
terraform output -raw ssh_command            # se connecter à la VM
sudo cat /var/log/vigie-bootstrap.log        # suivre cloud-init
test -f /var/lib/vigie/bootstrap.done        # cloud-init terminé
sudo k3s kubectl get nodes                   # nœud Ready
```

Pour piloter le cluster depuis le poste, le kubeconfig est copié dans
`~/.vigie/kubeconfig` (jamais dans le dépôt). Il pointe sur `https://127.0.0.1:6443`,
servi par un tunnel SSH :

```sh
terraform output -raw kube_tunnel_command    # à lancer dans un terminal dédié
KUBECONFIG=~/.vigie/kubeconfig kubectl get nodes
```

Une nouvelle image Ubuntu ou une modification de `cloud-init.sh` ne recrée pas la VM :
ces deux champs sont ignorés après la création. Reconstruire le nœud est une décision
explicite : `terraform apply -replace=oci_core_instance.vigie`.

## Manque de capacité (« Out of host capacity »)

La région `eu-paris-1` n'a qu'un domaine de disponibilité (vérifié avec
`oci iam availability-domain list`), donc changer `ad_number` ne sert à rien. Le quota
A1 du compte est disponible ; c'est la capacité physique d'Oracle qui manque par moments.
Le compte ne passe **jamais** en paiement à l'usage pour contourner le problème.

La tâche `infra-retry` relance `terraform apply` toutes les 10 minutes et s'arrête au
premier succès, à la première erreur qui n'est pas un manque de capacité, ou au bout de
sept jours (1 008 essais). Le journal, expurgé des OCID et des IP publiques, est écrit
dans `~/.vigie/terraform/retry.log`.

```sh
python tasks.py infra-retry
```

Intervalle et nombre d'essais se règlent par `VIGIE_INFRA_RETRY_INTERVAL_S` et
`VIGIE_INFRA_RETRY_MAX_ATTEMPTS`. Après sept jours sans capacité, le plan B s'applique :
cluster k3d sur le poste, `terraform plan` gardé comme preuve, enseignant prévenu.

## Destruction

Après la soutenance seulement : `terraform destroy`. Le bucket de sauvegardes doit être
vidé avant, Object Storage refusant de supprimer un bucket non vide.
