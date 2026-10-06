import pytest

from vigie.config import Settings
from vigie.corpus.models import Chunk
from vigie.corpus.parse import article_numbers, clean_id, parse_regulation
from vigie.corpus.sources import get_regulation

DORA = get_regulation("DORA")


def parse(excerpt: bytes, settings: Settings, **kwargs: bool) -> dict[str, Chunk]:
    chunks = parse_regulation(excerpt, DORA, settings, retrieved_on="2026-10-02", **kwargs)
    return {chunk.eid: chunk for chunk in chunks}


@pytest.fixture
def chunks(excerpt: bytes) -> dict[str, Chunk]:
    return parse(excerpt, Settings(_env_file=None, corpus_split_words=100))


def test_short_article_is_one_chunk_with_title_and_chapter(chunks: dict[str, Chunk]) -> None:
    article = chunks["art_1"]
    assert article.kind == "article"
    assert article.article == "1"
    assert article.paragraph is None
    assert article.title == "Objet"
    assert article.chapter == "CHAPITRE I - Dispositions générales"
    assert article.regulation == "DORA"
    assert article.celex == "32022R2554"
    assert article.retrieved_on == "2026-10-02"
    assert article.url.endswith("?uri=CELEX:32022R2554#art_1")


def test_paragraphs_and_nested_tables_become_labelled_lines(chunks: dict[str, Chunk]) -> None:
    lines = chunks["art_1"].text.split("\n")
    assert lines[0].startswith("1. Pour atteindre un niveau commun")
    assert lines[1] == "a) les exigences applicables aux entités financières en ce qui concerne:"
    assert lines[2] == "i) la gestion des risques liés aux TIC;"
    assert lines[3].startswith("2. Le présent règlement")


def test_no_break_spaces_are_normalized_and_note_calls_dropped(chunks: dict[str, Chunk]) -> None:
    text = chunks["art_1"].text
    assert " " not in text
    assert " " not in text
    assert "  " not in text
    assert text.endswith("du règlement (UE) no 648/2012.")
    assert "Il s’applique à partir du 17 janvier 2025." in chunks["art_64"].text


def test_article_without_numbered_paragraphs_keeps_its_free_text(
    chunks: dict[str, Chunk],
) -> None:
    assert chunks["art_64"].text.startswith("Le présent règlement entre en vigueur")


def test_chapter_is_found_through_a_section(chunks: dict[str, Chunk]) -> None:
    chapter = "CHAPITRE V - Gestion des risques liés aux prestataires tiers de services TIC"
    assert chunks["art_28.par_1"].chapter == chapter


def test_long_article_is_split_by_paragraph(chunks: dict[str, Chunk]) -> None:
    first, second = chunks["art_28.par_1"], chunks["art_28.par_2"]
    assert (first.paragraph, second.paragraph) == ("1", "2")
    # The sentence before paragraph 1 belongs with it, not in a chunk of its own.
    assert first.text.startswith("Les principes qui suivent")
    assert second.text.split("\n")[1].startswith("a) les accords contractuels")
    assert first.url == second.url
    assert first.url.endswith("#art_28")
    assert "art_28" not in chunks


def test_oversized_pieces_are_packed_into_parts(excerpt: bytes) -> None:
    chunks = parse(excerpt, Settings(_env_file=None, corpus_split_words=50))
    assert {"art_28.par_2.part_1", "art_28.par_2.part_2"} <= chunks.keys()
    assert chunks["art_28.par_2.part_2"].paragraph == "2"
    definitions = [eid for eid in chunks if eid.startswith("art_3.")]
    assert definitions == ["art_3.part_1", "art_3.part_2", "art_3.part_3"]
    assert all(chunks[eid].paragraph is None for eid in definitions)


def test_annex_is_indexed_with_its_title_and_table_rows(chunks: dict[str, Chunk]) -> None:
    annex = chunks["anx_I"]
    assert annex.kind == "annex"
    assert annex.article == "I"
    assert annex.title == "Liste indicative des variables de risque"
    assert "ANNEXE I" not in annex.text
    assert "Variable | Exemple | Poids" in annex.text
    assert "Clients | activités du bénéficiaire effectif | élevé" in annex.text
    assert annex.text.endswith("Texte libre hors paragraphe")
    # The published id carries a no-break space; the link must keep it to land on the anchor.
    assert annex.url.endswith("#anx_%C2%A0I")


def test_recitals_are_only_indexed_on_request(excerpt: bytes, chunks: dict[str, Chunk]) -> None:
    assert not any(chunk.kind == "recital" for chunk in chunks.values())
    with_recitals = parse(excerpt, Settings(_env_file=None), include_recitals=True)
    recital = with_recitals["rct_1"]
    assert recital.kind == "recital"
    assert recital.article == "1"
    assert recital.text.startswith("(1) À l’ère numérique")


def test_article_numbers_are_counted_once_whatever_the_split(chunks: dict[str, Chunk]) -> None:
    assert article_numbers(list(chunks.values())) == ["1", "64", "28", "3"]


def test_clean_id_removes_every_kind_of_space() -> None:
    assert clean_id("anx_ IV") == "anx_IV"


def test_text_after_the_last_paragraph_stays_with_it(chunks: dict[str, Chunk]) -> None:
    assert chunks["art_28.par_2"].text.endswith("à la disposition de l’autorité compétente.")


def test_article_outside_any_chapter_has_an_empty_chapter() -> None:
    xhtml = (
        b'<html><body><div class="eli-subdivision" id="art_1">'
        b'<p class="oj-ti-art">Article premier</p><p class="oj-normal">Objet.</p>'
        b"<!-- comment --></div></body></html>"
    )
    (chunk,) = parse_regulation(xhtml, DORA, Settings(_env_file=None), retrieved_on="d")
    assert (chunk.chapter, chunk.title, chunk.text) == ("", "", "Objet.")
