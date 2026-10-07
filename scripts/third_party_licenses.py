"""Third party licence inventory and policy.

Inputs are produced by tools, never typed by hand: pip-licenses (JSON) for the Python
packages of the API image, the web build (web/dist/third-party-licenses.json) for the npm
packages that actually ship, and docs/compliance/licences.yaml for what no tool can read
(models, datasets, service images), each entry with its primary source.

Usage:
  python scripts/third_party_licenses.py --python py.json --web web.json --out FILE
  python scripts/third_party_licenses.py ... --check   # fails on drift or a refused licence
Exit codes: 0 fine, 1 refused licence or file out of date, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

# EN: strong copyleft would spread to the proprietary code of the repository; it needs a
# written decision first (brief 11.12). LGPL is left out of this pattern on purpose: a
# Python import is dynamic linking. UNKNOWN is refused until a source is written down.
# FR : un copyleft fort contaminerait le code propriétaire du dépôt, il exige d'abord une
# décision écrite (brief 11.12). La LGPL est exclue exprès : un import Python est une
# liaison dynamique. UNKNOWN est refusé tant qu'aucune source n'est écrite.
REFUSED = re.compile(r"(?<!L)\bA?GPL|GNU General Public|Affero|SSPL|EUPL|CC-BY-NC|Commons Clause")

HEADER = """# Licences des composants tiers

Fichier généré par `scripts/third_party_licenses.py`, ne pas modifier à la main. Sources :
`pip-licenses` sur l'environnement d'exécution de l'API (Linux, `uv sync --frozen`, sans
extra), la liste des paquets npm réellement présents dans le build de l'interface
(`web/scripts/third-party-licenses.ts`) et `docs/compliance/licences.yaml` pour les modèles,
jeux de données et services, chacun avec sa source primaire.

Le code de Vigie reste sous la licence propriétaire de `LICENSE`. Aucun composant livré n'est
sous copyleft fort ; la CI le vérifie à chaque PR (job `licenses`). Les modèles et jeux de
données ne sont jamais copiés dans le dépôt.
"""


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def python_rows(
    packages: Sequence[Mapping[str, str]], overrides: Mapping[str, Any]
) -> list[dict[str, str]]:
    rows = []
    for pkg in sorted(packages, key=lambda p: p["Name"].lower()):
        name, licence, url = pkg["Name"], pkg["License"], pkg.get("URL", "")
        fixed = overrides.get(name)
        if licence in ("UNKNOWN", "") and fixed:
            licence, url = f"{fixed['license']} (vérifiée à la main)", fixed["source"]
        rows.append({"name": name, "version": pkg["Version"], "license": licence, "url": url})
    return rows


def web_rows(packages: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "name": p["name"],
            "version": p["version"],
            "license": p["license"],
            "url": p["repository"],
        }
        for p in sorted(packages, key=lambda p: p["name"])
    ]


def refused(rows: Sequence[Mapping[str, str]]) -> list[str]:
    return [
        f"{row['name']} {row['version']}: {row['license']}"
        for row in rows
        if row["license"] in ("UNKNOWN", "") or REFUSED.search(row["license"])
    ]


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def _table(head: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = [f"| {' | '.join(head)} |", f"|{'---|' * len(head)}"]
    lines += [f"| {' | '.join(_cell(c) for c in row)} |" for row in rows]
    return "\n".join(lines)


def render(
    py: Sequence[Mapping[str, str]], web: Sequence[Mapping[str, str]], manual: Mapping[str, Any]
) -> str:
    sections = [HEADER]
    for title, key in (("Modèles", "models"), ("Jeux de données et textes", "datasets")):
        entries = manual.get(key, [])
        body = _table(
            ["Nom", "Épinglage", "Rôle", "Licence", "Livraison", "Source"],
            [
                [e["name"], e["pin"], e["role"], e["license"], e["shipped"], e["source"]]
                for e in entries
            ],
        )
        sections.append(f"## {title}\n\n{body}\n")
    services = manual.get("services", [])
    body = _table(
        ["Nom", "Rôle", "Licence", "Source"],
        [[s["name"], s["role"], s["license"], s["source"]] for s in services],
    )
    sections.append(f"## Services et images\n\n{body}\n")
    for title, rows in (("Paquets Python de l'API", py), ("Paquets npm de l'interface", web)):
        body = _table(
            ["Paquet", "Version", "Licence", "Source"],
            [[r["name"], r["version"], r["license"], r["url"]] for r in rows],
        )
        sections.append(f"## {title} ({len(rows)})\n\n{body}\n")
    return "\n".join(sections)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--python", type=Path, required=True, help="pip-licenses JSON")
    parser.add_argument(
        "--web", type=Path, required=True, help="web/dist/third-party-licenses.json"
    )
    parser.add_argument("--manual", type=Path, default=Path("docs/compliance/licences.yaml"))
    parser.add_argument("--out", type=Path, default=Path("THIRD_PARTY_LICENSES.md"))
    parser.add_argument(
        "--check", action="store_true", help="compare with --out instead of writing"
    )
    args = parser.parse_args(argv)
    try:
        manual = yaml.safe_load(args.manual.read_text(encoding="utf-8"))
        py = python_rows(load_json(args.python), manual.get("overrides", {}))
        web = web_rows(load_json(args.web))
    except (OSError, ValueError, KeyError) as exc:
        print(f"unreadable input: {exc}", file=sys.stderr)
        return 2
    bad = refused([*py, *web])
    for line in bad:
        print(f"refused licence: {line}", file=sys.stderr)
    text = render(py, web, manual)
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        if current != text:
            print(f"{args.out} is out of date, regenerate it", file=sys.stderr)
            return 1
    else:
        args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(py)} Python and {len(web)} npm packages, {len(bad)} refused")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
