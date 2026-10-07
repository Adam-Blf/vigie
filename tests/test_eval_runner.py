import pytest
from tests.eval_fakes import thresholds
from tests.rag_fixtures import StubRetriever, passage
from tests.test_eval_retrieval import question

from vigie.evaluation.rag_eval import evaluate_rag
from vigie.evaluation.runner import build_report
from vigie.llm.fake import FakeLLM
from vigie.rag.pipeline import RagPipeline

PASSAGES = [passage("28", "1"), passage("30", "2"), passage("5", None)]


def pipeline(passages: list | None = None, hallucinate: bool = True) -> RagPipeline:  # type: ignore[type-arg]
    retriever = StubRetriever(PASSAGES if passages is None else passages)
    return RagPipeline(retriever, FakeLLM(hallucinate=hallucinate), top_k=3)


QUESTIONS = [
    question("a", ("DORA:28",)),
    question("b", ("DORA:12",)),
    question("out-dev", ()),
    question("out-test", (), split="test"),
    question("t", ("DORA:30",), split="test"),
]


def test_the_filter_is_proven_by_raw_validity_below_one_and_no_invented_citation() -> None:
    result = evaluate_rag(QUESTIONS, pipeline(), split="dev")

    # Three valid citations and one invented per answer, before the filter.
    assert result.raw_citation_validity == pytest.approx(0.75)
    assert result.invented_in_final_answer == 0
    assert result.citation_precision == pytest.approx(1 / 6)
    assert result.citation_coverage == pytest.approx(0.5)
    # Only the dev out-of-scope row counts on dev; the fake never refuses on its own.
    assert (result.refusal_rows, result.correct_refusal_rate) == (1, 0.0)
    assert result.rows[0].removed == ("DORA:999",)


def test_refusals_on_test_count_every_out_of_scope_row() -> None:
    result = evaluate_rag(QUESTIONS, pipeline(passages=[]), split="test")
    assert result.refusal_rows == 2
    assert result.correct_refusal_rate == 1.0
    assert [r.id for r in result.rows] == ["out-dev", "out-test", "t"]


def test_a_split_with_only_refusals_is_an_error_and_no_refusal_row_gives_none() -> None:
    with pytest.raises(ValueError, match="dev split"):
        evaluate_rag([question("out", ())], pipeline(), split="dev")
    result = evaluate_rag([question("a", ("DORA:28",))], pipeline(), split="dev")
    assert result.correct_refusal_rate is None


def test_the_report_holds_metrics_intervals_rows_and_config() -> None:
    config = {"embedding_model": "m"}
    report = build_report(
        QUESTIONS,
        StubRetriever(PASSAGES),
        split="dev",
        depth=5,
        thresholds=thresholds(),
        config=config,
        pipeline=pipeline(),
        llm="fake-llm",
    )

    assert report["split"] == "dev" and report["llm"] == "fake-llm"
    assert report["config"] == config
    assert report["metrics"]["recall_at_k"] == 0.5
    assert report["metrics"]["mrr"] == 0.5
    assert report["counts"] == {"retrieval_questions": 2, "rag_rows": 3, "refusal_rows": 1}
    interval = report["ci"]["recall_at_k"]
    assert interval["low"] <= interval["point"] <= interval["high"]
    assert set(report["ci"]) == {"recall_at_k", "mrr", "citation_precision", "citation_coverage"}
    assert report["retrieval_rows"][0]["id"] == "a"
    assert report["created_utc"].endswith("Z")


def test_without_a_pipeline_only_retrieval_is_measured() -> None:
    report = build_report(
        QUESTIONS,
        StubRetriever(PASSAGES),
        split="dev",
        depth=5,
        thresholds=thresholds(),
        config={},
        pipeline=None,
        llm="none",
    )
    assert set(report["metrics"]) == {"recall_at_k", "mrr"}
    assert report["rag_rows"] == [] and report["counts"]["rag_rows"] == 0
