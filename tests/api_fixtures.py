"""Shared builders for the API tests: a full app on temporary files, a fake model and
the DORA article 28 passages, with tokens ready to use."""

from __future__ import annotations

from collections.abc import Generator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from vigie.api.app import create_app
from vigie.api.factory import build_state
from vigie.api.state import AppState
from vigie.config import Settings
from vigie.guard.base import BlockReason, GuardDecision
from vigie.llm.base import ChatMessage, LLMClient, LLMError, LLMErrorKind, Usage
from vigie.llm.fake import FakeLLM
from vigie.rag.pipeline import Retriever
from vigie.rag.static_retriever import StaticRetriever

FIXTURES = Path(__file__).parent / "fixtures"
PASSAGES = FIXTURES / "dora_art28_passages.json"
QUESTION = "Quelles vérifications avant un accord avec un prestataire TIC ?"


class PhraseGuard:
    """Blocks on fixed phrases. The API tests check the plumbing around a decision; the
    real detectors are tested on their own, against the benchmark split."""

    def __init__(self, phrases: dict[str, BlockReason] | None = None) -> None:
        self.phrases = phrases or {"ignore tes instructions": "injection"}
        self.seen: list[str] = []

    def check(self, text: str) -> GuardDecision:
        self.seen.append(text)
        for phrase, reason in self.phrases.items():
            if phrase in text.lower():
                return GuardDecision(True, reason, (f"test_{reason}",), 1.0)
        return GuardDecision(False)


class FailingLLM(LLMClient):
    """Fails with a given kind, after an optional first delta."""

    def __init__(self, kind: LLMErrorKind, after_delta: bool = False) -> None:
        self.model = "failing-llm"
        self._kind = kind
        self._after_delta = after_delta

    def _deltas(self, messages: Sequence[ChatMessage]) -> Generator[str, None, Usage]:
        if self._after_delta:
            yield "début"
        raise LLMError(self._kind, "simulated failure")


def api_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "db_path": tmp_path / "vigie.sqlite3",
        "audit_dir": tmp_path / "audit",
        "audit_pod_name": "pod-a",
        "llm_provider": "fake",
        "bundle_version": "test-bundle",
        "cors_origins": ["http://127.0.0.1:4710"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@dataclass
class Api:
    client: TestClient
    state: AppState
    user_token: str
    admin_token: str

    def auth(self, token: str | None = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {token or self.user_token}"}

    def ask(self, question: str = QUESTION, **kwargs: Any) -> Any:
        return self.client.post(
            "/v1/ask", json={"question": question}, headers=self.auth(), **kwargs
        )


def make_api(
    tmp_path: Path,
    *,
    llm: LLMClient | None = None,
    guard: PhraseGuard | None = None,
    retriever: Retriever | None = None,
    **overrides: Any,
) -> Api:
    settings = api_settings(tmp_path, **overrides)
    state = build_state(
        settings,
        input_guard=guard or PhraseGuard(),
        retriever=retriever or StaticRetriever.from_json(PASSAGES),
        llm=llm or FakeLLM(),
    )
    client = TestClient(create_app(state))
    user = state.tokens.create("alice").secret
    admin = state.tokens.create("root", scope="admin").secret
    return Api(client, state, user, admin)
