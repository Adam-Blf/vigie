"""``vigie-quant`` console script, the J12 study end to end.

Subcommands:
  export  ONNX fp32 export at the pinned revision, then dynamic int8 quantization
  parity  check the fp32 graph against the PyTorch model on a padded batch
  embed   measure both variants on the dev split, log them to MLflow, write the decision
  llm     Ministral 3B Q4_K_M against Q8_0 through the local Ollama
  chart   draw docs/assets/quantization.png from the embedding results
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from functools import partial
from pathlib import Path

from vigie.config import Settings, get_settings
from vigie.evaluation.golden import load_golden
from vigie.quant.decision import load_threshold
from vigie.quant.dense import retrieval_questions
from vigie.quant.export import export_fp32, parity_gap, quantize_int8, variant_paths
from vigie.quant.llm_bench import OllamaProbe, select_questions
from vigie.quant.runner import (
    LogRun,
    embedding_payload,
    llm_items,
    run_embedding_study,
    run_llm_variant,
    write_json,
)
from vigie.quant.stats import file_size
from vigie.quant.study import Encoder, StudySettings, load_chunks
from vigie.quant.tracking import log_run


def _encoder(path: Path, tokenizer: Path, settings: Settings) -> Encoder:
    from vigie.quant.encoder import OnnxEncoder

    return OnnxEncoder.from_files(path, tokenizer, settings.dense_max_tokens)


def _logger(args: argparse.Namespace, settings: Settings) -> LogRun | None:
    if args.no_mlflow:
        return None
    return partial(log_run, tracking_uri=settings.mlflow_tracking_uri)


def _export(args: argparse.Namespace, settings: Settings) -> int:
    paths = export_fp32(settings.dense_model, settings.dense_model_revision, args.models)
    quantize_int8(paths, per_channel=not args.per_tensor)
    for path in (paths.fp32, paths.int8):
        print(f"{path.name}: {file_size(path)} bytes")
    return 0


# A short question and a long article sentence: the batch is padded, which is exactly the
# case a broken attention mask gets wrong.
PARITY_TEXTS = [
    "Qui est responsable du risque informatique ?",
    "L'organe de direction de l'entité financière définit, approuve, supervise et répond de "
    "la mise en oeuvre de toutes les dispositions relatives au cadre de gestion du risque.",
]


def _parity(args: argparse.Namespace, settings: Settings) -> int:
    paths = variant_paths(args.models)
    gap = parity_gap(settings.dense_model, settings.dense_model_revision, paths, PARITY_TEXTS)
    print(f"max abs gap between ONNX fp32 and PyTorch sentence vectors: {gap:.3e}")
    return 0 if gap <= args.tolerance else 1


def _print_table(rows: Mapping[str, Mapping[str, object]]) -> None:
    for name, row in rows.items():
        cells = ", ".join(f"{key}={value}" for key, value in row.items())
        print(f"{name}: {cells}")


def _embed(args: argparse.Namespace, settings: Settings) -> int:
    threshold = load_threshold(args.thresholds)
    paths = variant_paths(args.models)
    variants = {
        "fp32": (_encoder(paths.fp32, paths.tokenizer, settings), file_size(paths.fp32)),
        "int8": (_encoder(paths.int8, paths.tokenizer, settings), file_size(paths.int8)),
    }
    questions = retrieval_questions(load_golden(args.golden))
    study = StudySettings(
        k=threshold.k, warmup=settings.quant_warmup_queries, passes=settings.quant_latency_passes
    )
    results, decision = run_embedding_study(
        variants, load_chunks(args.corpus), questions, threshold, study, _logger(args, settings)
    )
    payload = embedding_payload(results, decision, threshold)
    write_json(args.results, payload)
    _print_table(payload["variants"])
    print(f"decision: deploy {decision.deployed}", *decision.reasons, sep="\n  ")
    return 0


def _llm(args: argparse.Namespace, settings: Settings) -> int:
    paths = variant_paths(args.models)
    variant = getattr(paths, settings.dense_variant)
    encoder = _encoder(variant, paths.tokenizer, settings)
    questions = select_questions(load_golden(args.golden), settings.quant_llm_questions)
    items = llm_items(encoder, load_chunks(args.corpus), questions, settings.top_k)
    options: dict[str, float | int] = {
        "num_ctx": settings.llm_num_ctx,
        "num_predict": settings.llm_num_predict,
        "temperature": settings.llm_temperature,
    }
    probe = OllamaProbe(settings.ollama_url, options, settings.quant_llm_timeout_s)
    variants: dict[str, object] = {}
    embedding = settings.dense_variant
    try:
        for model in args.model or settings.quant_llm_models:

            def save(answers: list[dict[str, object]], model: str = model) -> None:
                variants[model] = {"summary": None, "answers": answers}
                write_json(args.results, {"embedding_variant": embedding, "variants": variants})

            result, answers = run_llm_variant(
                probe, model, items, _logger(args, settings), on_answer=save
            )
            variants[model] = {"summary": asdict(result), "answers": answers}
            _print_table({model: asdict(result)})
    finally:
        probe.close()
    write_json(args.results, {"embedding_variant": embedding, "variants": variants})
    return 0


def _chart(args: argparse.Namespace, _: Settings) -> int:
    from vigie.quant.report import draw_chart

    payload = json.loads(args.results.read_text(encoding="utf-8"))
    print(draw_chart(payload, args.out))
    return 0


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vigie-quant", description="J12 quantization study")
    commands = parser.add_subparsers(dest="command", required=True)
    proofs = Path("docs/proofs/J12")

    export = commands.add_parser("export", help="export fp32 ONNX and quantize to int8")
    export.add_argument(
        "--per-tensor",
        action="store_true",
        help="one scale per tensor, the J12 export of MiniLM, instead of one per channel",
    )
    export.set_defaults(handler=_export)

    parity = commands.add_parser("parity", help="check the fp32 export against PyTorch")
    parity.add_argument("--tolerance", type=float, default=1e-4)
    parity.set_defaults(handler=_parity)

    embed = commands.add_parser("embed", help="measure fp32 and int8, write the decision")
    embed.add_argument("--thresholds", type=Path, default=settings.thresholds_path)
    embed.add_argument("--results", type=Path, default=proofs / "embedding-results.json")
    embed.set_defaults(handler=_embed)

    llm = commands.add_parser("llm", help="compare the Ollama quantizations of the LLM")
    llm.add_argument("--model", action="append", help="Ollama tag, repeatable")
    llm.add_argument("--results", type=Path, default=proofs / "llm-results.json")
    llm.set_defaults(handler=_llm)

    for sub in (export, parity, embed, llm):
        sub.add_argument("--models", type=Path, default=settings.quant_dir)
    for sub in (embed, llm):
        sub.add_argument("--golden", type=Path, default=settings.golden_path)
        sub.add_argument("--corpus", type=Path, default=settings.corpus_dir)
        sub.add_argument("--no-mlflow", action="store_true", help="skip the MLflow runs")

    chart = commands.add_parser("chart", help="draw the comparison chart")
    chart.add_argument("--results", type=Path, default=proofs / "embedding-results.json")
    chart.add_argument("--out", type=Path, default=Path("docs/assets/quantization.png"))
    chart.set_defaults(handler=_chart)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    args = build_parser(settings).parse_args(argv)
    code: int = args.handler(args, settings)
    return code
