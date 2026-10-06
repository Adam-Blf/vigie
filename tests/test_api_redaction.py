import logging

import pytest

from vigie.api.redaction import REDACTED, RedactionFilter, install, scrub

TOKEN = "vig_" + "A1b2C3d4" * 5


@pytest.mark.parametrize(
    "line",
    [
        f"headers: {{'authorization': 'Bearer {TOKEN}'}}",
        f"Authorization: Bearer {TOKEN}",
        f"authorization={TOKEN}",
        f"retrying with bearer {TOKEN}",
        f"token {TOKEN} rejected",
    ],
)
def test_scrub_removes_tokens(line: str) -> None:
    cleaned = scrub(line)
    assert TOKEN not in cleaned and REDACTED in cleaned


def test_scrub_leaves_ordinary_lines_alone() -> None:
    line = "POST /v1/ask 200 in 812 ms, trace_id=abc123"
    assert scrub(line) == line


def test_filter_handles_arguments_and_extra_fields() -> None:
    record = logging.LogRecord(
        "vigie.api", logging.INFO, __file__, 1, "auth with %s for %s", (TOKEN, "alice"), None
    )
    record.question = "Quel est mon solde ? IBAN FR76..."
    record.token = TOKEN
    assert RedactionFilter().filter(record) is True
    assert record.getMessage() == f"auth with {REDACTED} for alice"
    assert record.question == REDACTED and record.token == REDACTED


def test_installed_filter_cleans_what_handlers_write(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("vigie.test.redaction")
    handler = caplog.handler
    redaction = install("vigie.test.redaction")
    handler.addFilter(redaction)
    try:
        logger.warning("client sent Authorization: Bearer %s", TOKEN)
        logger.info("question received", extra={"question": "mon IBAN est FR76"})
    finally:
        handler.removeFilter(redaction)
        for name in ("", "vigie.test.redaction"):
            logging.getLogger(name).removeFilter(redaction)
            for h in logging.getLogger(name).handlers:
                h.removeFilter(redaction)
    assert TOKEN not in caplog.text
    assert all(getattr(r, "question", REDACTED) == REDACTED for r in caplog.records)
