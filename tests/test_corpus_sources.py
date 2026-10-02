import pytest

from vigie.config import Settings
from vigie.corpus.sources import REGULATIONS, cellar_url, eurlex_url, get_regulation


def test_registry_holds_the_four_texts_with_their_citation_codes() -> None:
    assert {r.code: r.celex for r in REGULATIONS} == {
        "DORA": "32022R2554",
        "AIACT": "32024R1689",
        "RGPD": "32016R0679",
        "AMLR": "32024R1624",
    }


def test_lookup_ignores_case_and_rejects_unknown_codes() -> None:
    assert get_regulation("rgpd").celex == "32016R0679"
    with pytest.raises(KeyError, match="DORA, AIACT, RGPD, AMLR"):
        get_regulation("GDPR")


def test_urls_use_https_and_anchor_on_the_article() -> None:
    settings = Settings(_env_file=None)
    dora = get_regulation("DORA")
    assert cellar_url(dora, settings) == (
        "https://publications.europa.eu/resource/celex/32022R2554"
    )
    base = "https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:32022R2554"
    assert eurlex_url(dora, settings) == base
    assert eurlex_url(dora, settings, "art_28") == f"{base}#art_28"
