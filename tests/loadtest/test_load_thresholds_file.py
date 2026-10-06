"""The load thresholds are written once, in eval/thresholds.yaml.

Settings keeps its own defaults so the API never needs the file at runtime, which means the
two can drift. These tests make a drift fail the build instead of silently judging a run
against numbers nobody agreed on.
"""

from pathlib import Path
from typing import Any

import yaml

from vigie.config import Settings
from vigie.loadtest.guard import REMOTE_MAX_USERS

THRESHOLDS_FILE = Path(__file__).resolve().parents[2] / "eval" / "thresholds.yaml"


def _load_section() -> dict[str, Any]:
    document = yaml.safe_load(THRESHOLDS_FILE.read_text(encoding="utf-8"))
    section = document["load"]
    assert isinstance(section, dict)
    return section


def test_settings_defaults_equal_the_thresholds_file() -> None:
    load = _load_section()
    settings = Settings(_env_file=None)
    assert settings.load_p95_ms == load["p95_ms"]
    assert settings.load_max_error_ratio == load["max_error_ratio"]
    assert settings.load_max_attack_leak_ratio == load["max_attack_leak_ratio"]


def test_remote_user_cap_equals_the_thresholds_file() -> None:
    assert _load_section()["remote_max_users"] == REMOTE_MAX_USERS


def test_load_section_holds_only_known_keys() -> None:
    assert set(_load_section()) == {
        "p95_ms",
        "max_error_ratio",
        "max_attack_leak_ratio",
        "remote_max_users",
    }
