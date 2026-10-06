from __future__ import annotations

import subprocess
from pathlib import Path

import check_coauthors as cc
import pytest

EMILIEN = "261297658+emilien754@users.noreply.github.com"
ADAM = "adam.beloucif@efrei.net"


def _commit(email: str, message: str, name: str = "Adam Beloucif") -> cc.Commit:
    return cc.Commit("a" * 40, name, email, message)


def test_parse_log_splits_records_and_keeps_multiline_bodies() -> None:
    raw = (
        f"abc\x1fAdam Beloucif\x1f{ADAM}\x1ffeat: one\n\nbody\n"
        f"Co-authored-by: Emilien Morice <{EMILIEN}>\n\x1e\n"
        f"def\x1fEmilien Morice\x1f{EMILIEN}\x1ffix: two\n\x1e\n"
    )
    commits = cc.parse_log(raw)
    assert [c.sha for c in commits] == ["abc", "def"]
    assert commits[0].message.startswith("feat: one\n\nbody")
    assert commits[1].author_email == EMILIEN


def test_parse_log_of_empty_output_is_empty() -> None:
    assert cc.parse_log("") == []


def test_coauthor_emails_is_case_insensitive_and_ignores_prose() -> None:
    message = (
        "feat: x\n\nWe talked about co-authored-by trailers here.\n"
        f"co-authored-BY:  Emilien Morice  <{EMILIEN.upper()}>\n"
        f"Co-authored-by: Adam Beloucif <{ADAM}>\n"
    )
    assert cc.coauthor_emails(message) == {EMILIEN, ADAM}


def test_adam_commit_with_trailer_credits_partner() -> None:
    commit = _commit(ADAM, f"feat: x\n\nCo-authored-by: Emilien Morice <{EMILIEN}>\n")
    assert cc.credits_partner(commit, cc.DEFAULT_PARTNER_EMAILS)


def test_school_address_in_trailer_also_counts() -> None:
    commit = _commit(ADAM, "feat: x\n\nCo-authored-by: Emilien Morice <emilien.morice@efrei.net>")
    assert cc.credits_partner(commit, cc.DEFAULT_PARTNER_EMAILS)


def test_emilien_as_author_needs_no_trailer() -> None:
    commit = _commit(EMILIEN, "docs: y", name="Emilien Morice")
    assert cc.credits_partner(commit, cc.DEFAULT_PARTNER_EMAILS)


def test_adam_commit_without_trailer_is_rejected() -> None:
    commit = _commit(ADAM, "feat: x\n\nCo-authored-by: Someone Else <someone@example.org>")
    assert not cc.credits_partner(commit, cc.DEFAULT_PARTNER_EMAILS)


def test_name_alone_without_matching_address_is_rejected() -> None:
    commit = _commit(ADAM, "feat: x\n\nCo-authored-by: Emilien Morice <emilien@typo.invalid>")
    assert not cc.credits_partner(commit, cc.DEFAULT_PARTNER_EMAILS)


def test_report_counts_missing_commits() -> None:
    good = _commit(EMILIEN, "docs: y", name="Emilien Morice")
    bad = _commit(ADAM, "feat: no trailer")
    lines, missing = cc.report([good, bad], cc.DEFAULT_PARTNER_EMAILS)
    assert missing == 1
    assert lines[0].startswith("ok")
    assert lines[1].startswith("MISSING")
    assert lines[-1] == "2 commit(s) checked, 1 without pair credit"


def test_report_handles_empty_message() -> None:
    lines, missing = cc.report([_commit(EMILIEN, "")], cc.DEFAULT_PARTNER_EMAILS)
    assert missing == 0
    assert lines[0].endswith("| ")


def _git(repo: Path, *args: str, email: str = ADAM, name: str = "Adam Beloucif") -> str:
    # Hooks are switched off so the user's own prepare-commit-msg hook cannot add a trailer.
    cmd = [
        "git",
        "-c",
        f"core.hooksPath={repo / 'no-hooks'}",
        "-c",
        f"user.name={name}",
        "-c",
        f"user.email={email}",
        "-c",
        "commit.gpgsign=false",
        *args,
    ]
    # Fixed argv built by the test itself, nothing comes from outside.
    done = subprocess.run(cmd, cwd=repo, check=True, capture_output=True, text=True)  # noqa: S603
    return done.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "chore: root")
    return tmp_path


def test_main_passes_on_credited_range(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _git(
        repo,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        f"feat: a\n\nCo-authored-by: Emilien Morice <{EMILIEN}>",
    )
    _git(
        repo, "commit", "-q", "--allow-empty", "-m", "docs: b", email=EMILIEN, name="Emilien Morice"
    )
    monkeypatch.chdir(repo)
    assert cc.main(["HEAD~2..HEAD"]) == 0
    assert "2 commit(s) checked, 0 without pair credit" in capsys.readouterr().out


def test_main_fails_on_commit_without_trailer(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _git(repo, "commit", "-q", "--allow-empty", "-m", "feat: lonely")
    monkeypatch.chdir(repo)
    assert cc.main(["HEAD~1..HEAD"]) == 1
    captured = capsys.readouterr()
    assert "MISSING" in captured.out
    assert "Co-authored-by" in captured.err


def test_main_accepts_custom_partner(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git(repo, "commit", "-q", "--allow-empty", "-m", "feat: x", email="other@example.org")
    monkeypatch.chdir(repo)
    assert cc.main(["HEAD~1..HEAD", "--partner-email", "OTHER@example.org"]) == 0


def test_main_reports_git_error(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(repo)
    assert cc.main(["nope..HEAD"]) == 2
    assert capsys.readouterr().err.startswith("error:")


def test_range_that_looks_like_an_option_is_refused() -> None:
    with pytest.raises(cc.GitError):
        cc.read_commits("--output=/tmp/x")
