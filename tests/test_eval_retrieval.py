import json
from pathlib import Path

import pytest
from tests.rag_fixtures import StubRetriever, passage
from tests.retrieval_fixtures import FakeEmbedder, indexed_settings

from vigie.evaluation import cli as eval_cli
from vigie.evaluation.golden import GoldenQuestion, dump_golden
from vigie.evaluation.retrieval_eval import evaluate_retrieval
from vigie.retrieval import factory


def question(qid: str, expected: tuple[str, ...], split: str = "dev") -> GoldenQuestion:
    return GoldenQuestion.model_validate(
        {
            "id": qid,
            "question": f"question {qid} article 28 DORA",
            "lang": "fr",
            "expected_articles": list(expected),
            "reference_answer": "réponse",
            "category": "in_scope" if expected else "out_of_scope",
            "status": "verified",
            "authored_by": "Emilien Morice",
            "verified_by": "Adam Beloucif",
            "split": split,
        }
    )


def test_metrics_count_distinct_articles_on_the_chosen_split() -> None:
    # Two paragraphs of article 28, then article 30: article 30 is second, not third.
    retriever = StubRetriever([passage("28", "1"), passage("28", "3"), passage("30", "1")])
    questions = [
        question("a", ("DORA:30",)),
        question("b", ("DORA:5",)),
        question("c", ()),
        question("d", ("DORA:28",), split="test"),
    ]

    result = evaluate_retrieval(questions, retriever, split="dev", k=1, depth=3)

    assert [r.id for r in result.rows] == ["a", "b"]
    assert result.rows[0].retrieved == ("DORA:28", "DORA:30")
    assert result.rows[0].reciprocal_rank == 0.5
    assert result.recall_at_k == 0.0
    assert result.mrr == 0.25
    assert retriever.calls[0][1] == 3
    assert result.as_dict()["questions"] == 2


def test_depth_below_k_is_refused() -> None:
    with pytest.raises(ValueError, match="depth"):
        evaluate_retrieval([], StubRetriever([]), split="dev", k=5, depth=4)


def test_a_split_without_any_expected_article_is_an_error() -> None:
    with pytest.raises(ValueError, match="dev split"):
        evaluate_retrieval([question("c", ())], StubRetriever([]), split="dev", k=1, depth=1)


def test_cli_runs_on_the_configured_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = indexed_settings(tmp_path)
    golden = tmp_path / "golden.jsonl"
    golden.write_text(
        dump_golden([question("a", ("DORA:28",)), question("t", ("RGPD:33",), split="test")]),
        encoding="utf-8",
    )
    monkeypatch.setattr(eval_cli, "get_settings", lambda: settings)
    monkeypatch.setattr(factory.FastEmbedEmbedder, "from_settings", lambda s: FakeEmbedder())
    out = tmp_path / "out" / "retrieval.json"

    code = eval_cli.main(["retrieval", "--golden", str(golden), "--k", "5", "--out", str(out)])

    assert code == 0
    printed = capsys.readouterr().out
    assert "split=dev questions=1 k=5 depth=20 recall@5=1.0000 mrr=1.0000" in printed
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["rows"][0]["id"] == "a"
    # Without --out nothing is written, the printed summary is the whole output.
    assert eval_cli.main(["retrieval", "--golden", str(golden)]) == 0
    assert "recall@5=1.0000" in capsys.readouterr().out
