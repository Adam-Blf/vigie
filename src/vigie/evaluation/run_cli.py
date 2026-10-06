"""``vigie-eval run``, ``gate``, ``register`` and ``alias``: the J8 evaluation loop.

run       evaluate the configured retriever (and the pipeline with the fake LLM), write
          the report, log it to MLflow
gate      check a report against eval/thresholds.yaml and, if given, the champion
register  create a `vigie-rag` version for a run, only if its gate passes
alias     show, set or remove the champion and challenger aliases
"""

from __future__ import annotations

import argparse
import json
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from vigie.config import Settings, get_settings
from vigie.corpus.jsonl import read_corpus_dir
from vigie.evaluation.bundle import run_config
from vigie.evaluation.gate import Check, passed, run_gate
from vigie.evaluation.golden import load_golden
from vigie.evaluation.mlflow_client import open_client
from vigie.evaluation.registry import (
    ALIASES,
    alias_report,
    register_version,
    remove_alias,
    run_report,
    set_alias,
    show_aliases,
)
from vigie.evaluation.runner import build_report
from vigie.evaluation.thresholds import load_thresholds
from vigie.evaluation.tracking import local_artifact_location, log_report
from vigie.llm.base import LLMClient
from vigie.llm.factory import build_llm
from vigie.llm.fake import FakeLLM
from vigie.rag.pipeline import RagPipeline
from vigie.retrieval.embeddings import FastEmbedEmbedder
from vigie.retrieval.factory import open_retriever, resolve_collection


def _llm(choice: str, settings: Settings) -> LLMClient:
    # The fake model invents one citation per answer, so every run also proves the filter.
    return FakeLLM(hallucinate=True) if choice == "fake" else build_llm(settings)


def _print_metrics(report: dict[str, Any]) -> None:
    for name, value in report["metrics"].items():
        shown = "n/a" if value is None else f"{value:.4f}"
        interval = report["ci"].get(name)
        bounds = f"  95 % CI [{interval['low']:.4f}, {interval['high']:.4f}]" if interval else ""
        print(f"  {name:<26} {shown}{bounds}")


def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    thresholds = load_thresholds(args.thresholds)
    questions = load_golden(args.golden)
    embedder = FastEmbedEmbedder.from_settings(settings)
    collection = resolve_collection(settings, embedder)
    with ExitStack() as stack:
        retriever = stack.enter_context(open_retriever(settings, embedder=embedder))
        pipeline = None
        llm_name = "none"
        if args.llm != "none":
            llm = stack.enter_context(_llm(args.llm, settings))
            llm_name = llm.model
            pipeline = RagPipeline(
                retriever,
                llm,
                top_k=settings.top_k,
                min_score=settings.rag_min_score,
                require_citation=settings.rag_require_citation,
            )
        config = run_config(
            settings,
            embedding_id=embedder.embedding_id,
            collection=collection,
            chunks=read_corpus_dir(settings.corpus_dir),
            llm=llm_name,
            depth=args.depth,
        )
        report = build_report(
            questions,
            retriever,
            split=args.split,
            depth=args.depth,
            thresholds=thresholds,
            config=config,
            pipeline=pipeline,
            llm=llm_name,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"split={report['split']} llm={llm_name} collection={collection}")
    _print_metrics(report)
    print(f"report: {args.out}")
    if args.no_mlflow:
        return 0
    client = open_client(args.tracking_uri)
    location = local_artifact_location(args.tracking_uri, settings.eval_artifact_dir)
    run_name = args.run_name or f"{report['split']}-{config['embedding_id']}"
    run_id = log_report(
        client, settings.eval_experiment, report, run_name=run_name, artifact_location=location
    )
    print(f"mlflow run: {run_id}")
    return 0


def _read_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _print_checks(checks: list[Check]) -> int:
    for check in checks:
        print(check.line())
    ok = passed(checks)
    print("gate PASSED" if ok else "gate FAILED")
    return 0 if ok else 1


def _gate(args: argparse.Namespace) -> int:
    settings = get_settings()
    report = _read_json(args.report)
    baseline = None
    if args.baseline:
        baseline = _read_json(args.baseline)
    elif args.champion:
        baseline = alias_report(
            open_client(args.tracking_uri), settings.eval_registered_model, "champion"
        )
    return _print_checks(run_gate(report, load_thresholds(args.thresholds), baseline))


def _register(args: argparse.Namespace) -> int:
    settings = get_settings()
    client = open_client(args.tracking_uri)
    name = settings.eval_registered_model
    report = run_report(client, args.run_id)
    checks = run_gate(
        report, load_thresholds(args.thresholds), alias_report(client, name, "champion")
    )
    if _print_checks(checks):
        print("not registered: a version is only created after the gate passes")
        return 1
    version, bundle = register_version(client, name, args.run_id, report, checks, settings)
    print(f"registered {name} version {version}, collection {bundle['qdrant_collection']}")
    if args.alias:
        set_alias(client, name, args.alias, version)
        print(f"alias {args.alias} -> version {version}")
    return 0


def _alias(args: argparse.Namespace) -> int:
    client = open_client(args.tracking_uri)
    name = get_settings().eval_registered_model
    if args.action == "set":
        if not args.version:
            print("alias set needs a version")
            return 2
        set_alias(client, name, args.alias, args.version)
    elif args.action == "remove":
        remove_alias(client, name, args.alias)
    for alias, version in show_aliases(client, name).items():
        print(f"{alias}: {version or '-'}")
    return 0


def add_commands(commands: Any, settings: Settings) -> None:
    def common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--thresholds", type=Path, default=settings.thresholds_path)
        sub.add_argument("--tracking-uri", default=settings.eval_tracking_uri)

    run = commands.add_parser("run", help="evaluate the configured setup and log it to MLflow")
    common(run)
    run.add_argument("--golden", type=Path, default=settings.golden_path)
    # dev by default for the same reason as `retrieval`: test is only for published figures.
    run.add_argument("--split", choices=["dev", "test"], default="dev")
    run.add_argument("--depth", type=int, default=20, help="passages asked per question")
    run.add_argument("--llm", choices=["fake", "configured", "none"], default="fake")
    run.add_argument("--out", type=Path, default=settings.eval_report_dir / "report.json")
    run.add_argument("--run-name")
    run.add_argument("--no-mlflow", action="store_true", help="write the report only")
    run.set_defaults(handler=_run)

    gate = commands.add_parser("gate", help="check a report against the floors")
    common(gate)
    gate.add_argument("--report", type=Path, required=True)
    source = gate.add_mutually_exclusive_group()
    source.add_argument("--baseline", type=Path, help="champion report as a JSON file")
    source.add_argument("--champion", action="store_true", help="read it from the registry")
    gate.set_defaults(handler=_gate)

    register = commands.add_parser("register", help="register a run that passes the gate")
    common(register)
    register.add_argument("run_id")
    register.add_argument("--alias", choices=ALIASES)
    register.set_defaults(handler=_register)

    alias = commands.add_parser("alias", help="show, set or remove an alias")
    alias.add_argument("--tracking-uri", default=settings.eval_tracking_uri)
    alias.add_argument("action", choices=["show", "set", "remove"])
    alias.add_argument("alias", nargs="?", choices=ALIASES, default="champion")
    alias.add_argument("version", nargs="?")
    alias.set_defaults(handler=_alias)
