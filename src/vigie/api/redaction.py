"""Keep tokens and question text out of the application logs.

Logs travel further than the audit log: they are scraped, shipped and pasted into
tickets. So the rule is absolute there: no Authorization header, no token, no question.
The filter rewrites every record before any handler formats it, whatever the logger.
"""

from __future__ import annotations

import logging
import re

REDACTED = "[REDACTED]"

_PATTERNS = (
    # Header dumps such as "authorization: Bearer abc" or "'Authorization': 'abc'".
    re.compile(r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?)(?:bearer\s+)?[^\s'\",}]+"),
    re.compile(r"(?i)(bearer\s+)[^\s'\",}]+"),
    re.compile(r"()vig_[A-Za-z0-9_-]{8,}"),
)
# Fields a caller might attach with extra={...}; their value is dropped, not scanned.
SENSITIVE_FIELDS = ("question", "answer", "token", "authorization")


def scrub(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}", text)
    return text


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Format once with the arguments, then scrub the result: a token passed as an
        # argument ("%s", token) would otherwise slip past a check on the template.
        record.msg = scrub(record.getMessage())
        record.args = None
        for name in SENSITIVE_FIELDS:
            if name in record.__dict__:
                setattr(record, name, REDACTED)
        return True


def install(*logger_names: str) -> RedactionFilter:
    """Attach one filter to the handlers of the given loggers and of the root logger.

    Handler filters, unlike logger filters, also see records propagated from child
    loggers, which is where third-party libraries log.
    """
    redaction = RedactionFilter()
    for name in ("", *logger_names):
        logger = logging.getLogger(name)
        logger.addFilter(redaction)
        for handler in logger.handlers:
            handler.addFilter(redaction)
    return redaction
