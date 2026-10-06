# Sécurité

## Signaler une vulnérabilité

Merci de ne pas ouvrir d'issue publique pour une faille. Écrivez à
adam.beloucif@efrei.net avec une description, les étapes pour la reproduire et
l'impact estimé. Nous accusons réception sous 72 heures et vous tenons informé de
la correction.

## Périmètre

Le code de ce dépôt, ses images publiées sur GHCR et l'instance de démonstration.
Vigie est un projet pédagogique : aucune donnée réelle de client ou de banque n'y est
traitée, et les jetons de démonstration sont révoqués après la soutenance.

## Ce que nous appliquons

- aucun secret dans le dépôt, gitleaks en pre-commit et en CI ;
- jetons d'accès stockés hachés, comparés à temps constant ;
- dépendances et images analysées à chaque build ;
- modèle de menace tenu à jour dans `docs/threat-model.md`.
