# ADR 0001. Hébergement à coût nul

- **Statut** : accepté
- **Date** : 2026-10-02
- **Auteurs** : Emilien Morice, Adam Beloucif

## Contexte

Vigie est un projet de cours mené par deux étudiants, sans budget. La grille demande
pourtant une vraie mise en production : VM créée par Terraform, Kubernetes avec scaling
horizontal, canary, test de charge en production, suivi MLflow. Une architecture
classique (Kubernetes managé, API de LLM facturée au token, base vectorielle hébergée)
coûte plusieurs dizaines d'euros par mois dès la première semaine, et une carte bancaire
liée à un compte cloud expose à une facture surprise si une ressource reste allumée.

Le binôme a donc fixé une contrainte dure avant tout choix technique : **zéro euro**,
aucune carte bancaire ajoutée nulle part, aucun passage d'un compte en mode payant.

## Décision

1. **Développement en local.** Tout le système se lance sur un poste avec
   `docker compose up` : API, Qdrant, LLM, MLflow, interface. Les ports sont liés à
   `127.0.0.1`.
2. **Production sur Oracle Cloud Always Free** : une VM Arm `VM.Standard.A1.Flex`
   (2 OCPU, 12 Go), créée par Terraform. Le choix d'Oracle est détaillé dans l'ADR 0002.
3. **LLM open-weight servi en local** par Ollama sur la VM, sans API externe. Détail dans
   l'ADR 0003.
4. **Embeddings locaux** avec fastembed (ONNX, sans torch) : modèle dense multilingue et
   modèle creux BM25, exécutés dans le processus de l'API ou du Job d'ingestion.
5. **k3s plutôt qu'un Kubernetes managé.** k3s tient dans environ 1,2 Go avec Traefik et
   CoreDNS, s'installe sur un seul nœud et suffit pour démontrer HPA, canary Argo Rollouts
   et NetworkPolicy. Un plan de contrôle managé n'existe pas en offre gratuite permanente.
6. **Faux LLM pour tout ce qui fait du volume.** Tests de charge, red teaming en CI et
   trafic de démonstration du canary passent par un fournisseur `fake` déterministe. Le
   LLM réel produit quelques tokens par seconde sur CPU Arm : le solliciter en charge ne
   mesurerait que sa file d'attente.
7. **Budget d'alerte** actif sur le compte Oracle, et destruction de l'infrastructure par
   `terraform destroy` après la soutenance.

## Conséquences

- **Positives.** Coût constaté nul, reproductible par n'importe quel lecteur du dépôt.
  Aucune donnée ne quitte l'infrastructure du binôme. L'architecture locale et la
  production partagent les mêmes images, ce qui limite les surprises au déploiement.
- **Négatives.** Un seul nœud : pas de haute disponibilité, et le scaling horizontal se
  démontre entre pods d'une même machine, pas entre machines. Le budget mémoire de 12 Go
  devient la contrainte qui arbitre tout (voir `docs/architecture.md`). Les images
  doivent être construites pour `linux/arm64`.
- **Risques.** La capacité Arm d'Oracle peut manquer au moment de créer la VM ; un
  réessai planifié et un plan B (cluster k3d sur le poste d'Adam) sont prévus. Les
  chiffres de charge mesurés avec le faux LLM décrivent l'API et les garde-fous, pas la
  génération : il faut le dire partout où ils sont publiés.
- **Révision.** Cette décision serait rouverte si un financement apparaissait ou si l'offre
  Always Free changeait de nouveau ses limites.
