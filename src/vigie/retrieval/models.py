"""What each dense model needs besides its name: input prefixes and, for some, a source.

The e5 family was trained with "query: " in front of questions and "passage: " in front of
documents. Without them the vectors still come out, only noticeably worse, and nothing
warns about it, so the prefixes are attached to the model name here instead of being left
to whoever writes the settings.

fastembed ships multilingual-e5-large but not the small and base sizes. Their authors
publish an ONNX export on the hub, which fastembed can load once told about it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DenseProfile:
    query_prefix: str = ""
    passage_prefix: str = ""


E5_PREFIXES = DenseProfile(query_prefix="query: ", passage_prefix="passage: ")

PROFILES: dict[str, DenseProfile] = {
    "intfloat/multilingual-e5-large": E5_PREFIXES,
    "intfloat/multilingual-e5-base": E5_PREFIXES,
    "intfloat/multilingual-e5-small": E5_PREFIXES,
}


@dataclass(frozen=True)
class CustomModel:
    """An ONNX export fastembed does not list, with what its pooling layer did."""

    dim: int
    size_in_gb: float
    model_file: str = "onnx/model.onnx"


CUSTOM_MODELS: dict[str, CustomModel] = {
    "intfloat/multilingual-e5-small": CustomModel(dim=384, size_in_gb=0.47),
    "intfloat/multilingual-e5-base": CustomModel(dim=768, size_in_gb=1.11),
}


def profile_for(model: str) -> DenseProfile:
    return PROFILES.get(model, DenseProfile())


def _fastembed_known() -> list[dict[str, Any]]:
    from fastembed import TextEmbedding

    known: list[dict[str, Any]] = TextEmbedding.list_supported_models()
    return known


def _fastembed_register(model: str, spec: CustomModel) -> None:
    from fastembed import TextEmbedding
    from fastembed.common.model_description import ModelSource, PoolingType

    # Mean pooling and L2 normalisation are what the e5 authors used; fastembed cannot
    # read that from the ONNX file, a wrong guess would still give vectors, only bad ones.
    TextEmbedding.add_custom_model(
        model=model,
        pooling=PoolingType.MEAN,
        normalization=True,
        sources=ModelSource(hf=model),
        dim=spec.dim,
        model_file=spec.model_file,
        size_in_gb=spec.size_in_gb,
    )


def register_custom_model(
    model: str,
    *,
    known: Callable[[], list[dict[str, Any]]] = _fastembed_known,
    register: Callable[[str, CustomModel], None] = _fastembed_register,
) -> bool:
    """Tell fastembed about `model` if it is one of ours; True when this call registered it.

    fastembed refuses a second registration of the same name, and the API builds its
    embedder once per process while the tests build many, hence the lookup first.
    """
    spec = CUSTOM_MODELS.get(model)
    if spec is None or any(entry["model"] == model for entry in known()):
        return False
    register(model, spec)
    return True
