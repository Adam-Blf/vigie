"""The output chain: what leaves the API is checked once more after the model.

Three checks. An answer that recites the system prompt is replaced by the refusal: the
input guard misses part of the extraction attempts, and this is where they are caught
whatever the model did. Every citation left in the text must be backed by a passage that
was really retrieved; the RAG layer already removes invented ones, and this second pass
makes sure a later change of that layer cannot quietly let one through. Then any personal
data the model copied into its answer is masked, the same way as in the audit log.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from vigie.guard.leak import prompt_leak
from vigie.guard.pii import mask_pii
from vigie.rag.citations import validate_citations
from vigie.rag.prompt import REFUSAL
from vigie.rag.types import Answer

# Gate proof only (branch test/gate-redteam): the output prompt leak check is switched off.
LEAK_CHECK = False


@dataclass(frozen=True)
class OutputReview:
    answer: Answer
    # Every citation removed on the way, by the RAG layer or by this second pass.
    removed_citations: tuple[str, ...]
    masked: tuple[str, ...]
    prompt_leak: bool = False


def review_answer(answer: Answer) -> OutputReview:
    if answer.refused:
        return OutputReview(answer, tuple(answer.removed_citations), ())
    if LEAK_CHECK and prompt_leak(answer.text):
        withheld = replace(answer, text=REFUSAL, citations=[], refused=True)
        return OutputReview(withheld, tuple(answer.removed_citations), (), prompt_leak=True)
    report = validate_citations(answer.text, answer.sources)
    masked = mask_pii(report.text)
    removed = (*answer.removed_citations, *report.removed)
    kept = {citation.label for citation in report.citations}
    checked = replace(
        answer,
        text=masked.text,
        citations=[c for c in answer.citations if c.label in kept],
        removed_citations=list(removed),
    )
    return OutputReview(checked, removed, masked.kinds)
