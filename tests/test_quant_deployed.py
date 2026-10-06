import json
from pathlib import Path

from vigie.config import Settings

ROOT = Path(__file__).resolve().parent.parent


def test_the_deployed_variant_is_the_study_outcome() -> None:
    settings = Settings(_env_file=None)
    results = json.loads((ROOT / "docs/proofs/J12/embedding-results.json").read_text("utf-8"))
    assert settings.dense_variant == results["decision"]["deployed"]
