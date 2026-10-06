from pathlib import Path

import numpy as np
import pytest

from quant_fixtures import CHUNKS, KeywordEncoder, chunk, question
from vigie.quant.dense import (
    chunk_article_ids,
    chunk_text,
    l2_normalize,
    mean_pool,
    rank_chunks,
    ranked_articles,
    retrieval_questions,
    score_retrieval,
)
from vigie.quant.stats import file_size, summarize_latency


def test_latency_summary_drops_the_warm_up_calls() -> None:
    samples = [500.0, 400.0] + [10.0] * 19 + [30.0]
    summary = summarize_latency(samples, warmup=2)
    assert summary.samples == 20
    assert summary.p50_ms == 10.0
    assert summary.p95_ms == pytest.approx(11.0)


@pytest.mark.parametrize(("samples", "warmup"), [([1.0], -1), ([1.0, 2.0], 2), ([], 0)])
def test_latency_summary_rejects_unusable_input(samples: list[float], warmup: int) -> None:
    with pytest.raises(ValueError):
        summarize_latency(samples, warmup)


def test_file_size_counts_external_weights(tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x" * 10)
    assert file_size(model) == 10
    (tmp_path / "m.onnx.data").write_bytes(b"y" * 5)
    assert file_size(model) == 15


def test_mean_pool_ignores_padding_tokens() -> None:
    tokens = np.array([[[1.0, 1.0], [3.0, 3.0], [100.0, 100.0]]], dtype=np.float32)
    mask = np.array([[1, 1, 0]], dtype=np.int64)
    assert mean_pool(tokens, mask).tolist() == [[2.0, 2.0]]


def test_mean_pool_survives_an_all_padding_row() -> None:
    tokens = np.ones((1, 2, 2), dtype=np.float32)
    assert mean_pool(tokens, np.zeros((1, 2), dtype=np.int64)).tolist() == [[0.0, 0.0]]


def test_l2_normalize_gives_unit_rows_and_keeps_zero_rows() -> None:
    out = l2_normalize(np.array([[3.0, 4.0], [0.0, 0.0]], dtype=np.float32))
    assert out[0].tolist() == pytest.approx([0.6, 0.8])
    assert out[1].tolist() == [0.0, 0.0]


def test_chunk_text_prefixes_the_title_when_there_is_one() -> None:
    plain = chunk("DORA", "5", "corps")
    assert chunk_text(plain) == "corps"
    assert chunk_text(plain.model_copy(update={"title": "Gouvernance"})) == "Gouvernance\ncorps"


def test_ranking_returns_distinct_articles_best_first() -> None:
    encoder = KeywordEncoder()
    documents = encoder.encode([chunk_text(c) for c in CHUNKS])
    query = encoder.encode(["qui dirige le risque tic ? direction"])[0]
    assert rank_chunks(query, documents, 2) == [0, 1]
    # Two DORA:5 chunks lead, they count once.
    ranking = ranked_articles(query, documents, chunk_article_ids(CHUNKS), depth=4)
    assert ranking[0] == "DORA:5"
    assert len(ranking) == len(set(ranking)) == 3


def test_retrieval_questions_keep_dev_rows_that_expect_articles() -> None:
    rows = [
        question("a", "q"),
        question("b", "q", split="test"),
        question("c", "q", expected=(), category="out_of_scope"),
    ]
    assert [q.id for q in retrieval_questions(rows)] == ["a"]


def test_score_retrieval_uses_the_shared_metrics() -> None:
    rows = [question("a", "q", ("DORA:5",)), question("b", "q", ("RGPD:83",))]
    score = score_retrieval([["DORA:5"], ["DORA:28", "RGPD:83"]], rows, k=5)
    assert score.recall_at_k == 1.0
    assert score.mrr == 0.75
    assert score.questions == 2


def test_score_retrieval_refuses_the_test_split_and_misaligned_input() -> None:
    with pytest.raises(ValueError, match="dev split only"):
        score_retrieval([["DORA:5"]], [question("a", "q", split="test")], k=5)
    with pytest.raises(ValueError, match="one ranking per question"):
        score_retrieval([], [question("a", "q")], k=5)
