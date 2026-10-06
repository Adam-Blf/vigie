"""Request and response shapes of the public API.

These models are the contract with the interface. docs/openapi.json is generated from
them and checked by a test, so a renamed field breaks the build here instead of the
interface in production.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vigie.guard.base import BlockReason

# Version of the HTTP contract, not of the application: it changes only when a client
# would have to change too.
CONTRACT_VERSION = "1.0.0"


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The 2 000 character cap mirrors VIGIE_MAX_QUESTION_CHARS; the route checks the
    # setting as well, so lowering it in production needs no new contract.
    question: str = Field(min_length=1, max_length=2000)


class CitationOut(BaseModel):
    label: str
    regulation: str
    article: str
    paragraph: str | None
    excerpt: str
    url: str


class AskResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    blocked: bool
    block_reason: BlockReason | None
    refused: bool
    # How many citations were removed for lack of a backing passage; the interface
    # shows "a reference that could not be verified was removed" when it is above 0.
    citations_removed: int
    trace_id: str
    app_version: str
    bundle_version: str
    prompt_version: str
    model: str
    latency_ms: float


class UsageOut(BaseModel):
    user: str
    requests: int
    blocked: int
    refused: int
    tokens_in: int
    tokens_out: int
    cost_eur: float
    requests_today: int
    daily_quota: int


class AdminUsageOut(BaseModel):
    users: list[UsageOut]


class ErrorOut(BaseModel):
    # A stable machine code and the trace id to quote; never a stack trace.
    error: str
    trace_id: str


class FieldError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ValidationErrorOut(ErrorOut):
    detail: list[FieldError]


class HealthOut(BaseModel):
    status: Literal["ok"]


class ReadyOut(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, bool]
