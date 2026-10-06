import pytest

from vigie.retrieval.references import ArticleRef, parse_references


def ids(question: str) -> list[str]:
    return [ref.article_id for ref in parse_references(question)]


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Que dit l'article 28 DORA ?", ["DORA:28"]),
        ("Art. 6 AI Act", ["AIACT:6"]),
        ("art 5 de l'AI Act", ["AIACT:5"]),
        ("DORA, articles 28 et 30", ["DORA:28", "DORA:30"]),
        ("Articles 9, 10 and 15 of the GDPR", ["RGPD:9", "RGPD:10", "RGPD:15"]),
        ("GDPR Article 17 erasure", ["RGPD:17"]),
        ("Article 99 of the Artificial Intelligence Act", ["AIACT:99"]),
        ("article 33 du règlement général sur la protection des données", ["RGPD:33"]),
        ("article 52 du règlement anti-blanchiment", ["AMLR:52"]),
        ("article 19 du règlement (UE) 2022/2554", ["DORA:19"]),
        ("l'article 50 du règlement sur l'IA", ["AIACT:50"]),
    ],
)
def test_explicit_references_are_found(question: str, expected: list[str]) -> None:
    assert ids(question) == expected


def test_each_number_goes_to_the_nearest_regulation() -> None:
    assert ids("art. 5 AI Act et art. 6 RGPD") == ["AIACT:5", "RGPD:6"]
    assert ids("RGPD article 28, puis DORA article 28") == ["RGPD:28", "DORA:28"]


@pytest.mark.parametrize(
    "question",
    [
        "Que dit l'article 28 ?",
        "article 28 a été modifié",
        "Quel registre une banque tient-elle sur ses prestataires selon DORA ?",
        "Une IA adorable doit-elle respecter l'article 5 ?",
        "The artificial intelligence of the article",
    ],
)
def test_no_reference_without_both_a_number_and_a_regulation(question: str) -> None:
    assert parse_references(question) == []


def test_duplicates_are_collapsed_in_order() -> None:
    assert parse_references("article 28 DORA, encore l'article 28 DORA") == [
        ArticleRef("DORA", "28")
    ]
