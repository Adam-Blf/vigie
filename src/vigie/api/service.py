"""One question, start to finish: normalize, guard, answer, check, count, audit.

The JSON route and the streaming route share every step here, so a question cannot be
guarded, counted or audited differently depending on how the client asked for it.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from vigie.api.auth import Principal
from vigie.api.errors import ApiError, retry_later
from vigie.api.schemas import AskResponse, CitationOut
from vigie.api.state import AppState
from vigie.api.usage import UsageEvent
from vigie.guard.base import GuardDecision
from vigie.guard.normalize import NormalizedInput, normalize
from vigie.guard.output import review_answer
from vigie.guard.pii import mask_pii
from vigie.llm.base import LLMError
from vigie.rag.pipeline import AnswerStream
from vigie.rag.types import Answer

log = logging.getLogger("vigie.api")

BLOCKED_ANSWER = "Cette question a été bloquée par les garde-fous de Vigie."

# A full queue or an unreachable model is worth retrying; a timeout is reported as such.
_LLM_STATUS = {"overloaded": 503, "unavailable": 503, "timeout": 504}


@dataclass(frozen=True)
class Screened:
    normalized: NormalizedInput
    decision: GuardDecision
    start: float


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class AskService:
    def __init__(self, state: AppState) -> None:
        self._s = state

    def _ms(self, start: float) -> float:
        return round((time.perf_counter() - start) * 1000, 1)

    def screen(self, question: str) -> Screened:
        start = time.perf_counter()
        normalized = normalize(question)
        decision = self._s.input_guard.check(normalized.guard_view)
        self._s.metrics.guard_latency.labels(self._s.bundle.bundle_version).observe(
            time.perf_counter() - start
        )
        return Screened(normalized, decision, start)

    def _response(self, screened: Screened, trace_id: str, answer: Answer | None) -> AskResponse:
        s = self._s
        decision = screened.decision
        return AskResponse(
            answer=answer.text if answer else BLOCKED_ANSWER,
            citations=[CitationOut(**vars(c)) for c in answer.citations] if answer else [],
            blocked=decision.blocked,
            block_reason=decision.reason if decision.blocked else None,
            refused=answer.refused if answer else False,
            citations_removed=len(answer.removed_citations) if answer else 0,
            trace_id=trace_id,
            app_version=s.settings.app_version,
            bundle_version=s.bundle.bundle_version,
            prompt_version=s.bundle.prompt_version,
            model=answer.model if answer and answer.model else s.model,
            latency_ms=self._ms(screened.start),
        )

    def _record(
        self,
        who: Principal,
        screened: Screened,
        trace_id: str,
        status: int,
        answer: Answer | None = None,
        error: str | None = None,
    ) -> None:
        s = self._s
        decision = screened.decision
        s.usage.record(
            UsageEvent(
                user=who.user,
                token_id=who.token_id,
                status=status,
                latency_ms=self._ms(screened.start),
                tokens_in=answer.tokens_in if answer else 0,
                tokens_out=answer.tokens_out if answer else 0,
                blocked=decision.blocked,
                refused=bool(answer and answer.refused),
            )
        )
        s.audit.write(
            {
                "trace_id": trace_id,
                "user": who.user,
                "status": status,
                "error": error,
                "question": mask_pii(screened.normalized.text).text,
                "answer": answer.text if answer else None,
                "citations": [c.label for c in answer.citations] if answer else [],
                "removed_citations": list(answer.removed_citations) if answer else [],
                "refused": bool(answer and answer.refused),
                "guard": {
                    "blocked": decision.blocked,
                    "reason": decision.reason,
                    "labels": list(decision.labels),
                    "score": decision.score,
                },
                "model": answer.model if answer and answer.model else s.model,
                "prompt_version": s.bundle.prompt_version,
                "bundle_version": s.bundle.bundle_version,
                "app_version": s.settings.app_version,
            }
        )

    def _count_answer(self, answer: Answer) -> None:
        version = self._s.bundle.bundle_version
        if answer.refused:
            self._s.metrics.refused.labels(version).inc()
        if answer.removed_citations:
            self._s.metrics.citations_removed.labels(version).inc(len(answer.removed_citations))

    def blocked(self, who: Principal, screened: Screened, trace_id: str) -> AskResponse:
        self._s.metrics.blocked.labels(
            self._s.bundle.bundle_version, screened.decision.reason or "other"
        ).inc()
        self._record(who, screened, trace_id, 200)
        return self._response(screened, trace_id, None)

    def reserve(self, who: Principal, screened: Screened, trace_id: str) -> None:
        """Take a generation slot, or refuse the request before any work is spent on it."""
        s = self._s
        if s.random() < s.bundle.fault_injection.error_rate:
            # The canary demo: a challenger with an error rate must fail like a real
            # broken build, so the client sees an ordinary internal error.
            s.metrics.errors.labels(s.bundle.bundle_version, "fault_injection").inc()
            self._record(who, screened, trace_id, 500, error="fault_injection")
            raise ApiError(500, "internal_error")
        if not s.llm_slots.acquire(blocking=False):
            s.metrics.llm_errors.labels(s.bundle.bundle_version, "busy").inc()
            self._record(who, screened, trace_id, 503, error="llm_busy")
            raise retry_later(503, "llm_busy", s.settings.retry_after_s)

    def _llm_failed(
        self, who: Principal, screened: Screened, trace_id: str, exc: LLMError
    ) -> ApiError:
        s = self._s
        s.metrics.llm_errors.labels(s.bundle.bundle_version, exc.kind).inc()
        status = _LLM_STATUS.get(exc.kind, 502)
        code = f"llm_{exc.kind}"
        self._record(who, screened, trace_id, status, error=code)
        if status == 503:
            return retry_later(status, code, s.settings.retry_after_s)
        return ApiError(status, code)

    def _finish(self, who: Principal, screened: Screened, trace_id: str, raw: Answer) -> Answer:
        answer = review_answer(raw).answer
        self._count_answer(answer)
        self._record(who, screened, trace_id, 200, answer)
        return answer

    def answer(self, who: Principal, screened: Screened, trace_id: str) -> AskResponse:
        """Blocking answer; reserve() must have succeeded."""
        try:
            raw = self._s.pipeline.answer(screened.normalized.text, trace_id)
        except LLMError as exc:
            raise self._llm_failed(who, screened, trace_id, exc) from exc
        finally:
            self._s.llm_slots.release()
        return self._response(screened, trace_id, self._finish(who, screened, trace_id, raw))

    def stream(self, who: Principal, screened: Screened, trace_id: str) -> Iterator[str]:
        """Server-sent events; reserve() must have succeeded.

        Deltas are the raw model output. The closing "answer" event carries the checked
        answer, which the client must display in place of the deltas.
        """
        try:
            stream: AnswerStream = self._s.pipeline.stream(screened.normalized.text, trace_id)
            for delta in stream:
                yield sse("delta", {"text": delta})
            answer = self._finish(who, screened, trace_id, stream.answer)
            yield sse("answer", self._response(screened, trace_id, answer).model_dump())
        except LLMError as exc:
            failure = self._llm_failed(who, screened, trace_id, exc)
            yield sse("error", {"error": failure.code, "trace_id": trace_id})
        except Exception:
            # Headers are already sent, so no status code can carry the failure any more:
            # the client gets a closing error event and the details stay in the server log.
            log.exception("stream failed, trace_id=%s", trace_id)
            self._s.metrics.errors.labels(self._s.bundle.bundle_version, "internal").inc()
            yield sse("error", {"error": "internal_error", "trace_id": trace_id})
        finally:
            self._s.llm_slots.release()
