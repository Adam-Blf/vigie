"""Draw docs/assets/retrieval-candidates.png from candidates.json, both in this folder.

Run from the repository root: python docs/proofs/J8/eval/chart.py
Two panels on the same 0 to 1 scale, recall@5 then MRR, one bar per candidate measured on
the dev split, the floor of eval/thresholds.yaml as a dashed line. The chosen candidate is
the dark bar; the others share one lighter step of the same blue.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[2] / "assets" / "retrieval-candidates.png"
CHOSEN, OTHER = "#184f95", "#86b6ef"
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"

data = json.loads((HERE / "candidates.json").read_text(encoding="utf-8"))
rows = data["candidates"]
labels = [r["label"] for r in rows]
colors = [CHOSEN if r.get("chosen") else OTHER for r in rows]

fig, axes = plt.subplots(1, 2, figsize=(11, 0.55 * len(rows) + 1.6), sharey=True)
fig.patch.set_facecolor(SURFACE)
for ax, metric, floor, title in (
    (axes[0], "recall_at_5", data["floors"]["recall_at_5"], "recall@5 (dev)"),
    (axes[1], "mrr", data["floors"]["mrr"], "MRR (dev)"),
):
    values = [r[metric] for r in rows]
    y = range(len(rows))
    ax.barh(list(y), values, color=colors, height=0.62, edgecolor=SURFACE, linewidth=2)
    ax.axvline(floor, color=MUTED, linestyle="--", linewidth=1.2)
    ax.text(
        floor,
        len(rows) - 0.35,
        f" seuil {floor:.2f}".replace(".", ","),
        color=MUTED,
        fontsize=8,
        va="bottom",
    )
    for i, v in enumerate(values):
        label = f"{v + 1e-9:.3f}".replace(".", ",")
        ax.text(
            v + 0.01,
            i,
            label,
            va="center",
            fontsize=8,
            color=INK,
            bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1.0},
        )
    ax.set_xlim(0, 1)
    ax.set_title(title, color=INK, fontsize=10, loc="left")
    ax.set_facecolor(SURFACE)
    ax.grid(axis="x", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
axes[0].set_yticks(list(range(len(rows))), labels)
axes[0].invert_yaxis()
fig.tight_layout()
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=150, facecolor=SURFACE)
print(OUT)
