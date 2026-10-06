"""python -m vigie.deploy.models, the model load check of the API image build."""

from __future__ import annotations

import io

import pytest

from retrieval_fixtures import FakeEmbedder
from vigie.config import Settings
from vigie.deploy import models
from vigie.guard.base import GuardDecision


class QuietGuard:
    def check(self, text: str) -> GuardDecision:
        return GuardDecision(False)


def test_check_runs_one_inference_per_model() -> None:
    out = io.StringIO()
    settings = Settings(_env_file=None, guard_classifier="off")
    models.check_models(settings, out, lambda _: FakeEmbedder(), lambda _: QuietGuard())
    report = out.getvalue()
    assert "embedding  fake-000000 dense=64" in report
    assert "guard      classifier=off blocked=False" in report


def test_main_reads_the_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Settings] = []
    monkeypatch.setattr(models, "check_models", lambda settings, out: seen.append(settings))
    assert models.main([]) == 0
    assert len(seen) == 1
