import pytest
from pydantic import ValidationError

from vigie.config import Settings


def test_redteam_gate_defaults_to_five_percent() -> None:
    assert Settings(_env_file=None).redteam_max_attack_success_rate == 0.05


def test_redteam_gate_rejects_rates_outside_zero_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_REDTEAM_MAX_ATTACK_SUCCESS_RATE", "1.5")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
