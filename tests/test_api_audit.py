import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from api_fixtures import make_api
from vigie.api import audit_cli
from vigie.api.audit import GENESIS, AuditLog, chain_hash, verify_chain
from vigie.config import get_settings


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


def lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_lines_are_chained_and_verify(tmp_path: Path) -> None:
    log = AuditLog(tmp_path, "pod-a", 30, clock=Clock())
    first = log.write({"trace_id": "a"})
    second = log.write({"trace_id": "b"})
    [one, two] = lines(log.directory / "2026-10-06.jsonl")
    assert one["prev"] == GENESIS and one["hash"] == first == chain_hash(one)
    assert two["prev"] == first and two["hash"] == second
    assert verify_chain(log.directory).ok


def test_modified_line_breaks_the_chain(tmp_path: Path) -> None:
    log = AuditLog(tmp_path, "pod-a", 30, clock=Clock())
    for trace in "abc":
        log.write({"trace_id": trace, "answer": "ok"})
    path = log.directory / "2026-10-06.jsonl"
    path.write_text(path.read_text(encoding="utf-8").replace('"answer":"ok"', '"answer":"no"', 1))
    report = verify_chain(log.directory)
    assert not report.ok and report.error == "2026-10-06.jsonl:1 was modified"


def test_removed_line_breaks_the_chain(tmp_path: Path) -> None:
    log = AuditLog(tmp_path, "pod-a", 30, clock=Clock())
    for trace in "abc":
        log.write({"trace_id": trace})
    path = log.directory / "2026-10-06.jsonl"
    kept = path.read_text(encoding="utf-8").splitlines()
    path.write_text(f"{kept[0]}\n{kept[2]}\n", encoding="utf-8")
    report = verify_chain(log.directory)
    assert not report.ok and "does not follow" in str(report.error)


def test_garbage_line_is_reported(tmp_path: Path) -> None:
    (tmp_path / "2026-10-06.jsonl").write_text("{not json\n", encoding="utf-8")
    assert verify_chain(tmp_path).error == "2026-10-06.jsonl:1 is not valid JSON"


def test_restart_continues_the_chain(tmp_path: Path) -> None:
    clock = Clock()
    last = AuditLog(tmp_path, "pod-a", 30, clock=clock).write({"trace_id": "a"})
    clock.now += timedelta(days=1)
    reopened = AuditLog(tmp_path, "pod-a", 30, clock=clock)
    reopened.write({"trace_id": "b"})
    assert lines(reopened.directory / "2026-10-07.jsonl")[0]["prev"] == last
    assert verify_chain(reopened.directory).ok


def test_purge_drops_days_past_retention_and_chain_still_verifies(tmp_path: Path) -> None:
    clock = Clock()
    log = AuditLog(tmp_path, "pod-a", 30, clock=clock)
    log.write({"trace_id": "old"})
    (log.directory / "notes.jsonl").write_text("", encoding="utf-8")
    clock.now += timedelta(days=31)
    log.write({"trace_id": "new"})  # first write of the day purges on its own
    names = sorted(p.name for p in log.directory.glob("*.jsonl"))
    assert names == ["2026-11-06.jsonl", "notes.jsonl"]
    assert verify_chain(log.directory).ok
    assert log.purge() == []


def test_pods_write_separate_files(tmp_path: Path) -> None:
    AuditLog(tmp_path, "pod-a", 30, clock=Clock()).write({"trace_id": "a"})
    AuditLog(tmp_path, "pod-b", 30, clock=Clock()).write({"trace_id": "b"})
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pod-a", "pod-b"]


def test_api_audit_line_has_decision_versions_and_masked_pii(tmp_path: Path) -> None:
    api = make_api(tmp_path)
    question = "Mon IBAN FR76 3000 6000 0112 3456 7890 189 et alice@example.com, DORA art. 28 ?"
    trace_id = api.ask(question).json()["trace_id"]
    [entry] = [e for f in api.state.audit.directory.glob("*.jsonl") for e in lines(f)]
    assert entry["trace_id"] == trace_id and entry["user"] == "alice"
    assert "FR76" not in str(entry["question"]) and "alice@example.com" not in str(entry)
    assert "[IBAN]" in str(entry["question"]) and "[EMAIL]" in str(entry["question"])
    assert entry["prompt_version"] and entry["bundle_version"] == "test-bundle"
    assert entry["guard"] == {"blocked": False, "reason": None, "labels": [], "score": 0.0}
    assert entry["citations"]
    assert not {"ip", "client", "user_agent", "headers"} & set(entry)


def run_cli(*args: str) -> tuple[int, str]:
    out = io.StringIO()
    return audit_cli.main(list(args), out=out), out.getvalue()


def test_audit_cli_verify_and_purge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIE_AUDIT_DIR", str(tmp_path))
    monkeypatch.setenv("VIGIE_AUDIT_POD_NAME", "pod-a")
    get_settings.cache_clear()
    try:
        AuditLog(tmp_path, "pod-a", 30).write({"trace_id": "a"})
        assert run_cli("verify") == (0, "chain intact, 1 line(s)\n")
        code, out = run_cli("purge")
        assert code == 0 and out.startswith("purged 0 file(s)")
        day = next((tmp_path / "pod-a").glob("*.jsonl"))
        day.write_text(day.read_text(encoding="utf-8").replace('"a"', '"b"'), encoding="utf-8")
        code, out = run_cli("verify")
        assert code == 1 and "was modified" in out
    finally:
        get_settings.cache_clear()
