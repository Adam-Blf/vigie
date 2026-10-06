"""The release bundle: the handful of values that define one version of Vigie in service.

In the cluster, the bundle is a JSON file mounted from an immutable ConfigMap written by
the delivery step from the MLflow registry. The API reads that file and never calls
MLflow itself: a registry outage must not take the service down, and a canary is just a
pod that mounts another bundle. Without a file, the bundle is built from the settings,
which is what local runs and tests use.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from vigie.config import LLMProvider, Settings
from vigie.rag.prompt import PROMPT_VERSION


class _Strict(BaseModel):
    # An unknown key is a typo in a ConfigMap, better caught at start than ignored.
    model_config = ConfigDict(extra="forbid", frozen=True)


class LLMSpec(_Strict):
    provider: LLMProvider
    model: str | None = None


class GuardSpec(_Strict):
    input_threshold: float = Field(ge=0.0, le=1.0)


class FaultInjection(_Strict):
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class Bundle(_Strict):
    bundle_version: str = Field(min_length=1)
    prompt_version: str
    top_k: int = Field(ge=1, le=20)
    llm: LLMSpec
    guard: GuardSpec
    fault_injection: FaultInjection = FaultInjection()


class BundleError(ValueError):
    """The bundle cannot serve with this build; the pod must not start."""


def from_settings(settings: Settings) -> Bundle:
    return Bundle(
        bundle_version=settings.bundle_version,
        prompt_version=PROMPT_VERSION,
        top_k=settings.top_k,
        llm=LLMSpec(provider=settings.llm_provider),
        guard=GuardSpec(input_threshold=settings.guard_input_threshold),
        fault_injection=FaultInjection(error_rate=settings.fault_error_rate),
    )


def load_bundle(settings: Settings) -> Bundle:
    if settings.bundle_path is None:
        bundle = from_settings(settings)
    else:
        bundle = Bundle.model_validate(json.loads(Path(settings.bundle_path).read_text("utf-8")))
    if bundle.prompt_version != PROMPT_VERSION:
        # The prompt is code. A bundle announcing another version would make every
        # answer, metric and evaluation run lie about what was actually sent.
        raise BundleError(
            f"bundle expects prompt {bundle.prompt_version}, this build ships {PROMPT_VERSION}"
        )
    return bundle


def llm_settings(settings: Settings, bundle: Bundle) -> Settings:
    """Settings with the bundle's LLM choice applied, for the LLM factory."""
    update: dict[str, object] = {"llm_provider": bundle.llm.provider}
    if bundle.llm.model is not None:
        key = "mistral_model" if bundle.llm.provider == "mistral" else "ollama_model"
        update[key] = bundle.llm.model
    return settings.model_copy(update=update)
