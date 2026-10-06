"""Locust scenario for POST /v1/ask: normal users, attackers and bursts.

Run it against an API started with VIGIE_LLM_PROVIDER=fake. The point is to measure our
own stack (auth, guards, retrieval), not how fast a 3B model generates tokens on a CPU,
which is measured separately. Protocol and thresholds: docs/load-test.md.

The token comes from VIGIE_LOAD_TOKEN and is never printed. The run is refused before the
first user spawns when it could hurt a deployment that is not this machine.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any

import gevent
from locust import HttpUser, between, events, task
from locust.clients import ResponseContextManager
from locust.env import Environment

from vigie.config import get_settings
from vigie.loadtest.guard import LoadGuardError, check_load_profile
from vigie.loadtest.questions import ATTACK_PROMPTS, normal_questions
from vigie.loadtest.verdict import LoadResult, LoadThresholds, violations

ASK_PATH = "/v1/ask"
# Attacks get their own stats row so a fast block cannot flatter the answering path p95.
ASK_NAME = "/v1/ask"
ATTACK_NAME = "/v1/ask [attack]"
# A burst user fires this many questions back to back, then goes quiet. It reproduces a
# user pasting a list of questions, which is what stresses the rate limiter.
BURST_SIZE = 5

log = logging.getLogger("vigie.load")
settings = get_settings()
QUESTIONS = normal_questions(settings.data_dir / "golden")


@dataclass
class AttackTally:
    judged: int = 0
    leaks: int = 0


ATTACKS = AttackTally()


def refuse_unsafe_runs(environment: Environment, **_: Any) -> None:
    """Stop the process before any request when the run breaks a safety rule.

    Locust treats an exception raised here as fatal and exits with code 1, which is the
    behaviour we want: nothing has been sent yet. The web UI is refused because users and
    host can be changed there after this check has run.
    """
    options = environment.parsed_options
    if options is None or not options.headless:
        raise LoadGuardError("run headless (--headless -u N), the web UI bypasses the guard")
    if settings.load_token is None:
        raise LoadGuardError("VIGIE_LOAD_TOKEN is not set")
    check_load_profile(environment.host, options.num_users or 1)
    log.info("load guard ok: %s users against %s", options.num_users or 1, environment.host)


def apply_verdict(environment: Environment, **_: Any) -> None:
    """Fail the process when a threshold is missed, like a red test would."""
    answering = environment.stats.get(ASK_NAME, "POST")
    total = environment.stats.total
    result = LoadResult(
        requests=total.num_requests,
        failures=total.num_failures,
        p95_ms=float(answering.get_response_time_percentile(0.95) or 0),
        attacks=ATTACKS.judged,
        attack_leaks=ATTACKS.leaks,
    )
    problems = violations(
        result,
        LoadThresholds(
            p95_ms=settings.load_p95_ms,
            max_error_ratio=settings.load_max_error_ratio,
            max_attack_leak_ratio=settings.load_max_attack_leak_ratio,
        ),
    )
    log.info(
        "verdict input: requests=%d failures=%d p95_ms=%.0f attacks=%d leaks=%d",
        result.requests,
        result.failures,
        result.p95_ms,
        result.attacks,
        result.attack_leaks,
    )
    if problems:
        for problem in problems:
            log.error("threshold missed: %s", problem)
        environment.process_exit_code = 1
    else:
        log.info("all load thresholds met")


def refresh_loop_clock(**_: Any) -> None:
    """Make --run-time last the time asked for.

    The libuv event loop caches its clock and only refreshes it when it turns. Locust arms
    the run-time timer right after this event, before the loop has turned since startup,
    so the timer started in the past: on Windows a 60 s run stopped after 53 s and an 8 s
    run after a tenth of a second. Refreshing the clock here fixes the start point.
    """
    gevent.get_hub().loop.update_now()


# Registered by call rather than decorator. EventHook.add_listener is unannotated, so under
# mypy --strict the decorator form makes each handler untyped, while the call form only
# reports the untyped call. Neither form makes Locust check a handler against the event's
# arguments, and load/ sits outside the mypy packages of pyproject.toml: the typed, tested
# logic lives in src/vigie/loadtest/. The clock refresh goes last so nothing runs between
# it and the timer.
events.init.add_listener(refuse_unsafe_runs)
events.init.add_listener(refresh_loop_clock)
events.quitting.add_listener(apply_verdict)


def _json_or_none(response: ResponseContextManager) -> dict[str, Any] | None:
    try:
        body = response.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


class AskUser(HttpUser):
    abstract = True

    def on_start(self) -> None:
        token = settings.load_token
        # The init guard already refused a missing token, this only narrows the type.
        assert token is not None  # noqa: S101
        self.client.headers["Authorization"] = f"Bearer {token.get_secret_value()}"

    def ask(self, question: str) -> None:
        with self.client.post(
            ASK_PATH, json={"question": question}, name=ASK_NAME, catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
            elif _json_or_none(response) is None:
                response.failure("body is not a JSON object")
            else:
                response.success()


class NormalUser(AskUser):
    """A compliance officer reading answers between questions."""

    weight = 7
    wait_time = between(1, 3)

    @task
    def ask_reference_question(self) -> None:
        self.ask(random.choice(QUESTIONS))  # noqa: S311 - traffic shaping, not security


class BurstUser(AskUser):
    """Several questions in a row, then a long pause."""

    weight = 1
    wait_time = between(8, 12)

    @task
    def ask_burst(self) -> None:
        for question in random.sample(QUESTIONS, k=min(BURST_SIZE, len(QUESTIONS))):
            self.ask(question)


class AttackerUser(AskUser):
    """Sends injection prompts and records the ones the input guard lets through."""

    weight = 2
    wait_time = between(2, 5)

    @task
    def inject(self) -> None:
        prompt = random.choice(ATTACK_PROMPTS)  # noqa: S311 - traffic shaping, not security
        with self.client.post(
            ASK_PATH, json={"question": prompt}, name=ATTACK_NAME, catch_response=True
        ) as response:
            body = _json_or_none(response) if response.status_code == 200 else None
            if body is None:
                response.failure(f"HTTP {response.status_code} or body not a JSON object")
                return
            ATTACKS.judged += 1
            if body.get("blocked") is not True:
                # A leak is a guard quality issue, judged by its own threshold, so the
                # request itself is not counted as an availability error.
                ATTACKS.leaks += 1
            response.success()
