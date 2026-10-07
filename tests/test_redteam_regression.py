"""Every red teaming bypass ever found stays in data/regression/ and is replayed here.

The API runs with the production regex guard (the classifier needs its 244 MB model and is
measured elsewhere) and a fake model that recites its system prompt on every answer, the
worst case for an attack that gets past the input guard. Each attack must end blocked or
refused, and no answer may carry a piece of the system prompt.
"""

import json
from pathlib import Path
from typing import Any

from api_fixtures import make_api
from vigie.guard.chain import InputChain
from vigie.guard.leak import prompt_leak
from vigie.llm.fake import FakeLLM

REGRESSION = Path(__file__).resolve().parents[1] / "data" / "regression" / "redteam.jsonl"
ROWS: list[dict[str, Any]] = [
    json.loads(line) for line in REGRESSION.read_text(encoding="utf-8").splitlines() if line.strip()
]


def test_regression_set_is_well_formed() -> None:
    assert len(ROWS) >= 40
    ids = [row["id"] for row in ROWS]
    assert len(ids) == len(set(ids))
    for row in ROWS:
        assert row["prompt"].strip() and row["found"] and row["plugin"] and row["strategy"]


def test_known_bypasses_never_leak_the_system_prompt(tmp_path: Path) -> None:
    api = make_api(tmp_path, guard=InputChain(), llm=FakeLLM(leak=True), rate_limit_per_minute=1000)
    leaks = []
    for row in ROWS:
        body = api.ask(row["prompt"][:2000]).json()
        stopped = body["blocked"] is True or body["refused"] is True
        if not stopped or prompt_leak(body["answer"]):
            leaks.append(row["id"])
    assert leaks == [], f"bypasses that leak again: {leaks}"


def test_a_legitimate_question_still_gets_an_answer_from_a_clean_model(tmp_path: Path) -> None:
    body = make_api(tmp_path, guard=InputChain()).ask().json()
    assert body["blocked"] is False and body["refused"] is False and body["citations"]
