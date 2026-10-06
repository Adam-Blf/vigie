from dataclasses import replace

import pytest

from rag_fixtures import passage
from vigie.guard.base import strongest
from vigie.guard.output import review_answer
from vigie.guard.pii import luhn_valid, mask_pii
from vigie.rag.citations import validate_citations
from vigie.rag.types import Answer, Timings


@pytest.mark.parametrize(
    ("text", "masked", "kind"),
    [
        ("écrire à jean.dupont@example.com svp", "écrire à [EMAIL] svp", "email"),
        ("IBAN FR76 3000 6000 0112 3456 7890 189.", "IBAN [IBAN].", "iban"),
        ("iban fr7630006000011234567890189", "iban [IBAN]", "iban"),
        ("carte 4111 1111 1111 1111 expirée", "carte [CARTE] expirée", "card"),
        ("appeler le 01 99 00 12 34", "appeler le [TÉLÉPHONE]", "phone"),
        ("ou +33 1 99 00 12 34", "ou [TÉLÉPHONE]", "phone"),
    ],
)
def test_obvious_personal_data_is_masked(text: str, masked: str, kind: str) -> None:
    result = mask_pii(text)
    assert result.text == masked and result.kinds == (kind,)


def test_numbers_that_are_not_personal_data_stay() -> None:
    text = "Article 28, CELEX 32022R2554, référence 1234 5678 9012 3456, 2 000 caractères."
    assert mask_pii(text).text == text


def test_luhn() -> None:
    assert luhn_valid("4111111111111111") and not luhn_valid("4111111111111112")


def test_strongest_reason_wins() -> None:
    assert strongest({"pii", "jailbreak"}) == "jailbreak"
    assert strongest({"pii"}) == "pii"
    assert strongest(set()) is None


def answer_for(text: str, refused: bool = False) -> Answer:
    sources = [passage("28", "1")]
    report = validate_citations(text, sources)
    return Answer(report.text, report.citations, sources, refused, "t", Timings())


def test_output_review_keeps_backed_citations_and_masks_pii() -> None:
    answer = answer_for("Contactez dpo@example.com [DORA art. 28 §1].")
    review = review_answer(answer)
    assert review.answer.text == "Contactez [EMAIL] [DORA art. 28 §1]."
    assert [c.label for c in review.answer.citations] == ["[DORA art. 28 §1]"]
    assert review.masked == ("email",) and review.removed_citations == ()


def test_output_review_catches_a_citation_slipped_in_after_the_rag_layer() -> None:
    answer = answer_for("Texte [DORA art. 28 §1].")
    tampered = replace(answer, text=answer.text + " Voir aussi [RGPD art. 99].")
    review = review_answer(tampered)
    assert "[RGPD art. 99]" not in review.answer.text
    assert review.removed_citations == ("[RGPD art. 99]",)
    assert review.answer.removed_citations == ["[RGPD art. 99]"]


def test_refusal_passes_through_untouched() -> None:
    answer = answer_for("Je ne trouve pas de réponse dans les textes indexés.", refused=True)
    assert review_answer(answer).answer is answer
