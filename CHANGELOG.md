# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions en
[SemVer](https://semver.org/lang/fr/). Chaque version publiée a sa release GitHub, dont
les notes reprennent la section correspondante.

## [Unreleased]

### Changed

- Bandeau de badges du README réduit à sept badges cohérents et centrés.

### Added

- Licence propriétaire, tous droits réservés, dépôt public en consultation seule.

## [0.1.0] - 2026-10-02

### Added

- Squelette du dépôt : paquets `vigie` et `guardbench`, configuration centralisée dans
  `src/vigie/config.py`, lanceur de tâches `tasks.py`.
- Outillage qualité : ruff, mypy strict, pytest avec couverture, pre-commit avec gitleaks.
- Hook de co-auteur du binôme sur chaque commit local.
- CI qualité sur chaque pull request et sur `main`, `main` protégée par un ruleset.
- Suivi de progression dans `docs/progress.md` et preuve du J0 outillage.
- README avec badges, ligne de version et architecture en Mermaid coloré, compatible avec
  le rendu de GitHub.
- Politique de sécurité `SECURITY.md` avant le passage du dépôt en public.
- Synchronisation de la version du README depuis `pyproject.toml`
  (`scripts/sync_version.py`) et notes de release tirées du CHANGELOG
  (`scripts/release_notes.py`).
- Workflow de release sur tag `vX.Y.Z` : contrôle du tag, wheel et sdist joints, images
  publiées sur GHCR dès que les Dockerfiles existent.
