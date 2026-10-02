"""Ask one question over a JSON file of passages, with the configured LLM.

    python -m vigie.rag.cli --passages tests/fixtures/dora_art28_passages.json "question"

The answer streams to stderr as it is generated, and the validated Answer is printed to
stdout as JSON, so the command doubles as the latency proof of the local model.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import TextIO

from vigie.config import get_settings
from vigie.llm.factory import build_llm
from vigie.rag.pipeline import RagPipeline
from vigie.rag.prompt import PROMPT_VERSION
from vigie.rag.static_retriever import StaticRetriever


def main(
    argv: Sequence[str] | None = None, out: TextIO = sys.stdout, live: TextIO = sys.stderr
) -> int:
    parser = argparse.ArgumentParser(prog="python -m vigie.rag.cli", description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--passages", type=Path, required=True)
    args = parser.parse_args(argv)

    settings = get_settings()
    pipeline = RagPipeline(
        StaticRetriever.from_json(args.passages),
        build_llm(settings),
        top_k=settings.top_k,
        min_score=settings.rag_min_score,
        require_citation=settings.rag_require_citation,
    )
    stream = pipeline.stream(args.question)
    for delta in stream:
        live.write(delta)
        live.flush()
    live.write("\n")

    report: dict[str, object] = {"question": args.question, "prompt_version": PROMPT_VERSION}
    report.update(asdict(stream.answer))
    out.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
