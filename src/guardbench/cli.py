"""Command line: `guardbench run --guards regex,deberta` and `guardbench validate`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx

from guardbench.datasets import Sample, load_deepset, load_seed
from guardbench.guards import GUARD_NAMES, build_guards
from guardbench.report import plot_quality_latency, write_csv, write_markdown
from guardbench.runner import GuardRun, run_all
from guardbench.validation import validate_seed
from vigie.config import Settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="guardbench", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="benchmark guards on the seed set")
    run.add_argument("--guards", default=",".join(GUARD_NAMES), help="comma-separated names")
    run.add_argument("--seed", type=Path, default=None, help="seed JSONL path")
    run.add_argument("--split", choices=["dev", "test", "all"], default="test")
    run.add_argument("--deepset", action="store_true", help="also run the deepset control set")
    run.add_argument("--out", type=Path, default=None, help="output directory")
    run.add_argument("--no-mlflow", action="store_true", help="skip MLflow logging")
    validate = sub.add_parser("validate", help="check the seed set rules")
    validate.add_argument("--seed", type=Path, default=None)
    return parser


def _publish(runs: Sequence[GuardRun], out: Path, title: str) -> list[Path]:
    paths = [out / "results.csv", out / "report.md", out / "quality_latency.png"]
    write_csv(runs, paths[0])
    write_markdown(runs, paths[1], title)
    plot_quality_latency(runs, paths[2])
    return paths


def _print_summary(runs: Sequence[GuardRun]) -> None:
    for run in runs:
        if run.in_scope is None:
            print(f"{run.name:<11} skipped: {run.skipped_reason}")
            continue
        m = run.in_scope
        print(
            f"{run.name:<11} f1={m.f1:.3f} recall={m.recall:.3f} fpr={m.fpr:.3f} "
            f"p95={m.p95_ms:.1f}ms errors={run.errors}"
        )


def _benchmark(
    samples: Sequence[Sample], dataset: str, out: Path, args: argparse.Namespace, s: Settings
) -> None:
    with httpx.Client(timeout=s.bench_http_timeout_s) as client:
        guards = build_guards([g for g in args.guards.split(",") if g], s, client)
        runs = run_all(guards, samples, s.bench_warmup_calls)
    artifacts = _publish(runs, out, f"Benchmark des garde-fous, jeu {dataset}")
    print(f"[{dataset}] {len(samples)} samples, outputs in {out}")
    _print_summary(runs)
    if not args.no_mlflow:
        from guardbench.tracking import log_runs

        log_runs(runs, s.mlflow_tracking_uri, s.bench_mlflow_experiment, dataset, artifacts)


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    args = _parser().parse_args(argv)
    s = settings or Settings()
    seed_path = args.seed or s.bench_seed_path
    if args.command == "validate":
        problems = validate_seed(load_seed(seed_path))
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"{seed_path}: {'invalid' if problems else 'valid'}")
        return 1 if problems else 0
    out = args.out or s.bench_output_dir
    split = None if args.split == "all" else args.split
    _benchmark(load_seed(seed_path, split), f"seed-{args.split}", out / "seed", args, s)
    if args.deepset:
        control = load_deepset(s.bench_deepset_repo)
        _benchmark(control, "deepset-test", out / "deepset", args, s)
    return 0
