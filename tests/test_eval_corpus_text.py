import json
from pathlib import Path

import pytest

from vigie.evaluation.corpus_text import (
    load_chunks_dir,
    load_corpus,
    load_xhtml_dir,
    normalize_space,
    parse_xhtml_articles,
)
from vigie.evaluation.regulations import article_id, split_article_id

# Same shape as the Official Journal markup served by Cellar, cut down to two articles.
XHTML = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<div class="eli-subdivision" id="art_6">
<p class="oj-ti-art">Article 6</p>
<div class="eli-title"><p class="oj-sti-art">Licéité du traitement</p></div>
<div id="006.001">
<p class="oj-normal">1.   Le traitement n'est licite que si:</p>
<table><tbody><tr>
<td><p class="oj-normal">a)</p></td>
<td><p class="oj-normal">la personne a <span>consenti</span> ;</p></td>
</tr></tbody></table>
</div>
</div>
<div class="eli-subdivision" id="art_12a"><p class="oj-normal">Article 12 bis</p></div>
<div class="eli-subdivision" id="rct_3"><p class="oj-normal">Considérant</p></div>
</body></html>
"""


def test_normalize_space_folds_non_breaking_spaces() -> None:
    assert normalize_space(" a  b c\n d ") == "a b c d"


def test_article_ids_round_trip() -> None:
    assert article_id("DORA", "28") == "DORA:28"
    assert split_article_id("DORA:28") == ("DORA", "28")


@pytest.mark.parametrize("value", ["DORA28", "XYZ:1", "DORA:", ":5"])
def test_malformed_article_ids_are_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="malformed"):
        split_article_id(value)


def test_xhtml_articles_keep_point_letters_apart_from_text() -> None:
    articles = parse_xhtml_articles("RGPD", XHTML)
    assert set(articles) == {"RGPD:6", "RGPD:12a"}
    text = articles["RGPD:6"]
    assert text.startswith("Article 6 Licéité du traitement 1. Le traitement")
    assert "a) la personne a consenti ;" in text


def test_xhtml_dir_maps_files_by_celex(tmp_path: Path) -> None:
    (tmp_path / "32016R0679.xhtml").write_text(XHTML, encoding="utf-8")
    (tmp_path / "99999X9999.xhtml").write_text(XHTML, encoding="utf-8")
    assert set(load_xhtml_dir(tmp_path)) == {"RGPD:6", "RGPD:12a"}


def test_xhtml_dir_reads_the_ingest_cache_names(tmp_path: Path) -> None:
    (tmp_path / "32016R0679.fra.xhtml").write_text(XHTML, encoding="utf-8")
    assert set(load_xhtml_dir(tmp_path)) == {"RGPD:6", "RGPD:12a"}


def test_xhtml_dir_without_known_file_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="32022R2554.xhtml"):
        load_xhtml_dir(tmp_path)


def _write_chunks(path: Path, chunks: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(c) + "\n" for c in chunks) + "\n", encoding="utf-8")


def test_chunks_of_one_article_are_joined(tmp_path: Path) -> None:
    base = {"title": "t", "chapter": "c", "url": "u", "eid": "e", "paragraph": None}
    _write_chunks(
        tmp_path / "dora.jsonl",
        [
            {**base, "regulation": "DORA", "article": "28", "text": "Premier  alinéa."},
            {**base, "regulation": "DORA", "article": "28", "text": "Second alinéa."},
            {**base, "regulation": "DORA", "article": 30, "text": "Autre."},
        ],
    )
    corpus = load_chunks_dir(tmp_path)
    assert corpus == {"DORA:28": "Premier alinéa. Second alinéa.", "DORA:30": "Autre."}


def test_unreadable_chunk_names_file_and_line(tmp_path: Path) -> None:
    (tmp_path / "bad.jsonl").write_text('{"regulation": "DORA"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"bad.jsonl:1"):
        load_chunks_dir(tmp_path)


def test_empty_chunk_dir_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_chunks_dir(tmp_path)


def test_load_corpus_prefers_chunks_over_xhtml(tmp_path: Path) -> None:
    (tmp_path / "32016R0679.xhtml").write_text(XHTML, encoding="utf-8")
    assert "RGPD:6" in load_corpus(tmp_path)
    _write_chunks(tmp_path / "rgpd.jsonl", [{"regulation": "RGPD", "article": "7", "text": "x"}])
    assert set(load_corpus(tmp_path)) == {"RGPD:7"}
