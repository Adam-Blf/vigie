import pytest

from rag_fixtures import passage
from vigie.rag.citations import (
    EXCERPT_CHARS,
    RawCitation,
    extract_citations,
    find_support,
    validate_citations,
)
from vigie.rag.labels import eurlex_url


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[DORA art. 28 §1]", RawCitation("DORA", "28", "1")),
        ("[RGPD art. 6]", RawCitation("RGPD", "6", None)),
        ("[dora article 28, § 3]", RawCitation("DORA", "28", "3")),
        ("[AIACT art. 5 paragraphe 2]", RawCitation("AIACT", "5", "2")),
        ("[AMLR art.12a par. 4b]", RawCitation("AMLR", "12a", "4b")),
        ("[NIS2 art. 21]", RawCitation("NIS2", "21", None)),
        # Ministral 3B wrote these during the J3 measurement: a point under a paragraph.
        ("[DORA art. 28 §4 a]", RawCitation("DORA", "28", "4")),
        ("[DORA art. 28 §4, point c)]", RawCitation("DORA", "28", "4")),
        ("[DORA art. 28 §1 b) ii)]", RawCitation("DORA", "28", "1")),
        ("[DORA art. 28 §4(e)]", RawCitation("DORA", "28", "4")),
    ],
)
def test_extracts_label_variants(text: str, expected: RawCitation) -> None:
    assert extract_citations(f"Une phrase {text}.") == [expected]


def test_point_under_a_paragraph_is_cited_at_paragraph_level() -> None:
    report = validate_citations(
        "Évaluer les risques :\n   [DORA art. 28 §4 c].", [passage("28", "4")]
    )
    assert report.text == "Évaluer les risques :\n   [DORA art. 28 §4]."
    assert [c.label for c in report.citations] == ["[DORA art. 28 §4]"]


def test_ignores_brackets_that_are_not_citations() -> None:
    assert extract_citations("Voir [note 3] et [DORA] ou [art. 28].") == []


def test_label_is_canonical() -> None:
    assert RawCitation("DORA", "28", "1").label == "[DORA art. 28 §1]"
    assert RawCitation("RGPD", "6", None).label == "[RGPD art. 6]"


def test_valid_citation_is_kept_with_its_source() -> None:
    report = validate_citations("Les entités gèrent ce risque [DORA art. 28 §1].", [passage()])
    assert report.text == "Les entités gèrent ce risque [DORA art. 28 §1]."
    assert [c.label for c in report.citations] == ["[DORA art. 28 §1]"]
    citation = report.citations[0]
    assert citation.url == eurlex_url("DORA")
    assert citation.excerpt.startswith("Les entités financières")
    assert (citation.regulation, citation.article, citation.paragraph) == ("DORA", "28", "1")
    assert report.removed == []
    assert report.raw_valid_rate == 1.0


def test_invented_citation_is_removed_and_reported() -> None:
    text = "Première règle [DORA art. 28 §1]. Autre règle [DORA art. 999 §9]."
    report = validate_citations(text, [passage()])
    assert report.text == "Première règle [DORA art. 28 §1]. Autre règle."
    assert report.removed == ["[DORA art. 999 §9]"]
    assert (report.raw_total, report.raw_valid) == (2, 1)
    assert report.raw_valid_rate == 0.5


def test_citation_to_a_regulation_outside_the_corpus_is_removed() -> None:
    report = validate_citations("Règle [NIS2 art. 21].", [passage()])
    assert report.text == "Règle."
    assert report.citations == []


def test_wrong_paragraph_is_invalid() -> None:
    report = validate_citations("Règle [DORA art. 28 §5].", [passage("28", "1")])
    assert report.removed == ["[DORA art. 28 §5]"]


def test_article_level_passage_backs_any_of_its_paragraphs() -> None:
    whole = passage("28", None)
    assert find_support(RawCitation("DORA", "28", "5"), [passage("28", "1"), whole]) is whole


def test_citation_without_paragraph_is_backed_by_any_passage_of_the_article() -> None:
    report = validate_citations("Règle [DORA art. 28].", [passage("28", "3")])
    assert [c.label for c in report.citations] == ["[DORA art. 28]"]


def test_same_regulation_is_required() -> None:
    assert find_support(RawCitation("RGPD", "28", "1"), [passage("28", "1")]) is None


def test_non_canonical_label_is_rewritten_and_deduplicated() -> None:
    text = "A [dora article 28, § 1]. B [DORA art. 28 §1]."
    report = validate_citations(text, [passage()])
    assert report.text == "A [DORA art. 28 §1]. B [DORA art. 28 §1]."
    assert len(report.citations) == 1
    assert report.raw_valid == 2


def test_rate_is_none_without_any_citation() -> None:
    report = validate_citations("Pas de citation.", [passage()])
    assert report.raw_valid_rate is None
    assert report.citations == []


def test_long_passage_gives_a_bounded_excerpt() -> None:
    long_text = "mot " * 200
    report = validate_citations("Règle [DORA art. 28 §1].", [passage(text=long_text)])
    excerpt = report.citations[0].excerpt
    assert excerpt.endswith("...")
    assert len(excerpt) <= EXCERPT_CHARS + 3
