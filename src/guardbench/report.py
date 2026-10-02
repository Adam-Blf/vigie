"""Benchmark outputs: a CSV for machines, a Markdown table for people, one chart.

The chart puts p95 latency on a log scale because the candidates span three orders of
magnitude, from a regex in microseconds to a SaaS round trip in hundreds of ms.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

from guardbench.datasets import CATEGORIES
from guardbench.metrics import Metrics
from guardbench.runner import GuardRun

CSV_FIELDS = (
    "guard",
    "scope",
    "n",
    "precision",
    "recall",
    "f1",
    "fpr",
    "p50_ms",
    "p95_ms",
    "errors",
    *(f"rate_{c}" for c in CATEGORIES),
)


def _row(run: GuardRun, scope: str, m: Metrics) -> dict[str, str]:
    row = {
        "guard": run.name,
        "scope": scope,
        "n": str(m.n),
        "precision": f"{m.precision:.3f}",
        "recall": f"{m.recall:.3f}",
        "f1": f"{m.f1:.3f}",
        "fpr": f"{m.fpr:.3f}",
        "p50_ms": f"{m.p50_ms:.2f}",
        "p95_ms": f"{m.p95_ms:.2f}",
        "errors": str(run.errors),
    }
    for category in CATEGORIES:
        rate = m.by_category.get(category)
        row[f"rate_{category}"] = "" if rate is None else f"{rate:.3f}"
    return row


def write_csv(runs: Sequence[GuardRun], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for run in runs:
            if run.overall and run.in_scope:
                writer.writerow(_row(run, "overall", run.overall))
                writer.writerow(_row(run, "in_scope", run.in_scope))


def markdown_table(runs: Sequence[GuardRun]) -> str:
    lines = [
        "| Outil | Périmètre | F1 global | F1 périmètre | Rappel | FPR benign "
        "| FPR benign_tricky | p50 (ms) | p95 (ms) | Erreurs |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        if not (run.overall and run.in_scope):
            lines.append(f"| {run.name} | non testé : {run.skipped_reason} |||||||||")
            continue
        m, s = run.overall, run.in_scope
        lines.append(
            f"| {run.name} | {', '.join(sorted(run.covers))} | {m.f1:.2f} | {s.f1:.2f} "
            f"| {s.recall:.2f} | {m.by_category.get('benign', 0.0):.1%} "
            f"| {m.by_category.get('benign_tricky', 0.0):.1%} | {m.p50_ms:.1f} "
            f"| {m.p95_ms:.1f} | {run.errors} |"
        )
    return "\n".join(lines) + "\n"


def category_table(runs: Sequence[GuardRun]) -> str:
    ran = [r for r in runs if r.overall]
    lines = [
        "| Catégorie | " + " | ".join(r.name for r in ran) + " |",
        "|---|" + "---|" * len(ran),
    ]
    for category in CATEGORIES:
        cells = []
        for run in ran:
            rate = run.overall.by_category.get(category) if run.overall else None
            cells.append("" if rate is None else f"{rate:.0%}")
        lines.append(f"| {category} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def write_markdown(runs: Sequence[GuardRun], path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        f"# {title}\n\n## Synthèse\n\n{markdown_table(runs)}\n"
        f"## Taux de signalement par catégorie\n\n{category_table(runs)}"
    )
    path.write_text(body, encoding="utf-8", newline="\n")


def plot_quality_latency(runs: Sequence[GuardRun], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=150)
    for run in runs:
        if run.in_scope is None:
            continue
        # A log axis cannot place zero; a regex can report a p95 that rounds to it.
        latency = max(run.in_scope.p95_ms, 0.01)
        ax.scatter(latency, run.in_scope.f1, s=60, color="#1f5f8b", zorder=3)
        ax.annotate(
            run.name,
            (latency, run.in_scope.f1),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=9,
        )
    ax.set_xscale("log")
    ax.set_xlabel("Latence p95 (ms, échelle logarithmique)")
    ax.set_ylabel("F1 dans le périmètre annoncé")
    ax.set_ylim(0, 1.05)
    ax.grid(True, which="both", linestyle=":", linewidth=0.6, color="#b8c2cc")
    ax.set_title("Garde-fous : qualité contre latence")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
