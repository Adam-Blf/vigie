"""The comparison chart of docs/quantization.md, drawn from the JSON results.

Two panels side by side, one bar per variant: what quantization saves (size, latency) and
what it may cost (recall@5, MRR). Values are printed on the bars so the figure reads
without the table next to it.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

# Two neutral, colour-blind safe tones: fp32 the reference, int8 the candidate.
COLOURS = {"fp32": "#5B6770", "int8": "#C8702A"}


def chart_series(payload: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """Per variant: size in MB, p95 latency in ms, recall@k and MRR in percent."""
    series: dict[str, dict[str, float]] = {}
    for name, result in payload["variants"].items():
        series[name] = {
            "Taille (Mo)": round(result["size_bytes"] / 1e6, 1),
            "Latence p95 (ms)": round(result["latency_p95_ms"], 1),
            "Rappel@5 (%)": round(result["recall_at_k"] * 100, 1),
            "MRR (%)": round(result["mrr"] * 100, 1),
        }
    return series


def draw_chart(payload: Mapping[str, Any], out: Path) -> Path:
    import matplotlib  # quant extra, imported lazily

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    series = chart_series(payload)
    groups = (("Taille (Mo)", "Latence p95 (ms)"), ("Rappel@5 (%)", "MRR (%)"))
    titles = ("Ce que la quantization économise", "Ce qu'elle peut coûter")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), dpi=150)
    width = 0.38
    for ax, metrics, title in zip(axes, groups, titles, strict=True):
        for offset, name in enumerate(series):
            values = [series[name][m] for m in metrics]
            xs = [i + (offset - 0.5) * width for i in range(len(metrics))]
            bars = ax.bar(xs, values, width, label=name, color=COLOURS.get(name, "#888888"))
            ax.bar_label(bars, fmt="%.1f", fontsize=8, padding=2)
        ax.set_xticks(range(len(metrics)), metrics)
        ax.set_title(title, fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
        ax.margins(y=0.15)
    axes[0].legend(frameon=False)
    fig.suptitle("Modèle d'embedding, fp32 contre int8 (partie dev du jeu de référence)")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    return out
