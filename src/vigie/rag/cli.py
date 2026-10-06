"""Ask one question with the configured retriever and LLM.

    python -m vigie.rag.cli "question"
    python -m vigie.rag.cli --passages tests/fixtures/dora_art28_passages.json "question"

Without --passages the retriever comes from VIGIE_RETRIEVER: qdrant by default, which
searches the collection built by vigie-index. --passages replays a JSON file of passages
instead, to measure the model alone.

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
from vigie.retrieval.factory import open_retriever


def main(
    argv: Sequence[str] | None = None, out: TextIO = sys.stdout, live: TextIO = sys.stderr
) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m vigie.rag.cli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("question")
    parser.add_argument("--passages", type=Path, help="JSON file of fixed passages")
    args = parser.parse_args(argv)

    settings = get_settings()
    # Both blocks close what they opened: the HTTP client of the real LLM providers, and
    # the Qdrant client, whose local mode keeps its folder locked while it is open.
    with open_retriever(settings, passages=args.passages) as retriever, build_llm(settings) as llm:
        pipeline = RagPipeline(
            retriever,
            llm,
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
