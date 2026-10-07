import json
from pathlib import Path

import pytest
import third_party_licenses as tpl
import yaml

MANUAL = {
    "overrides": {"stemmer": {"license": "MIT", "source": "https://example.org/stemmer"}},
    "models": [
        {
            "name": "m",
            "pin": "rev",
            "role": "r",
            "license": "Apache-2.0",
            "shipped": "s",
            "source": "u",
        }
    ],
    "datasets": [],
    "services": [{"name": "svc", "role": "r", "license": "MIT", "source": "u"}],
}


def write_inputs(tmp_path: Path, py: list[dict[str, str]]) -> list[str]:
    (tmp_path / "py.json").write_text(json.dumps(py), encoding="utf-8")
    web = [{"name": "preact", "version": "11.0.0", "license": "MIT", "repository": "x"}]
    (tmp_path / "web.json").write_text(json.dumps(web), encoding="utf-8")
    (tmp_path / "manual.yaml").write_text(yaml.safe_dump(MANUAL), encoding="utf-8")
    return [
        "--python",
        str(tmp_path / "py.json"),
        "--web",
        str(tmp_path / "web.json"),
        "--manual",
        str(tmp_path / "manual.yaml"),
        "--out",
        str(tmp_path / "OUT.md"),
    ]


def pkg(name: str, licence: str) -> dict[str, str]:
    return {"Name": name, "Version": "1.0", "License": licence, "URL": "https://x"}


def test_permissive_inventory_is_written_then_checked(tmp_path: Path) -> None:
    args = write_inputs(tmp_path, [pkg("fastapi", "MIT"), pkg("stemmer", "UNKNOWN")])
    assert tpl.main(args) == 0
    text = (tmp_path / "OUT.md").read_text(encoding="utf-8")
    assert "| stemmer | 1.0 | MIT (vérifiée à la main) | https://example.org/stemmer |" in text
    assert "## Paquets npm de l'interface (1)" in text and "| m | rev |" in text
    assert tpl.main([*args, "--check"]) == 0


@pytest.mark.parametrize(
    "licence",
    ["GPL-3.0-only", "GNU General Public License v3 (GPLv3)", "AGPL-3.0", "SSPL-1.0", "UNKNOWN"],
)
def test_copyleft_or_unknown_licence_fails(tmp_path: Path, licence: str) -> None:
    assert tpl.main(write_inputs(tmp_path, [pkg("bad", licence)])) == 1


def test_lgpl_and_mpl_are_accepted() -> None:
    rows = [
        {"name": n, "version": "1", "license": lic, "url": ""}
        for n, lic in (("a", "LGPL-3.0-or-later"), ("b", "MPL-2.0 AND MIT"))
    ]
    assert tpl.refused(rows) == []


def test_stale_file_fails_the_check(tmp_path: Path) -> None:
    args = write_inputs(tmp_path, [pkg("fastapi", "MIT")])
    (tmp_path / "OUT.md").write_text("old\n", encoding="utf-8")
    assert tpl.main([*args, "--check"]) == 1


def test_unreadable_input_exits_2(tmp_path: Path) -> None:
    args = write_inputs(tmp_path, [pkg("fastapi", "MIT")])
    (tmp_path / "py.json").write_text("not json", encoding="utf-8")
    assert tpl.main(args) == 2
