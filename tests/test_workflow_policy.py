"""Supply chain rules of the GitHub workflows, checked on the text so no YAML parser is needed.

actionlint proves the workflows are valid. These tests prove they stay pinned and least
privileged, which actionlint does not check: a workflow can be perfectly valid and still run
an action by a movable tag with write access to the repository.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GITHUB_DIR = ROOT / ".github"
WORKFLOWS = sorted((GITHUB_DIR / "workflows").glob("*.yml"))
ACTIONS = sorted((GITHUB_DIR / "actions").glob("*/action.yml"))

USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<ref>\S+)(?P<rest>.*)$")
PINNED_RE = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def _uses(path: Path) -> list[tuple[str, str]]:
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = USES_RE.match(line)
        if match:
            found.append((match.group("ref"), match.group("rest")))
    return found


def test_there_is_something_to_check() -> None:
    names = {path.name for path in WORKFLOWS}
    assert {"ci.yml", "build.yml"} <= names


@pytest.mark.parametrize("path", WORKFLOWS + ACTIONS, ids=lambda p: p.parent.name + "/" + p.name)
def test_every_action_is_pinned_by_full_sha_with_its_tag(path: Path) -> None:
    for ref, rest in _uses(path):
        if ref.startswith("./"):
            continue
        assert PINNED_RE.match(ref), f"{path.name}: {ref} is not pinned by a full commit SHA"
        # The tag comment is what Dependabot and a human reviewer read to know the version.
        assert re.search(r"#\s*v\d", rest), f"{path.name}: {ref} has no version comment"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_is_least_privileged_and_serialized(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "pull_request_target" not in text
    assert re.search(r"^permissions:\n  contents: read\n", text, re.M), "default must be read"
    assert re.search(r"^concurrency:\n", text, re.M)


def test_no_latest_tag_is_published() -> None:
    build = (GITHUB_DIR / "workflows" / "build.yml").read_text(encoding="utf-8")
    assert "latest=false" in build
    assert ":latest" not in build
    assert "linux/amd64,linux/arm64" in build


def test_no_kubeconfig_reaches_github() -> None:
    for path in WORKFLOWS:
        assert "kubeconfig" not in path.read_text(encoding="utf-8").lower()
