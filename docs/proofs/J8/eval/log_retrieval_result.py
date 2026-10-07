"""Log a finished `vigie-eval retrieval --out` result as one run of the vigie-eval experiment.

The reranked candidate (e5-large then jina-reranker-v2) takes about 73 s per question on
the workstation. Its measurement went through `vigie-eval retrieval`; the second pass
through `vigie-eval run` died after 50 minutes without writing anything. Rather than burn
another hour, this script logs the result already measured, with the same parameters,
the same bootstrap and a `source` tag that says where the numbers come from.

PYTHONPATH=src python docs/proofs/J8/eval/log_retrieval_result.py RESULT.json RUN_NAME \
    KEY=VALUE ...
"""

import json
import sys
from pathlib import Path

from vigie.config import Settings
from vigie.evaluation.mlflow_client import open_client
from vigie.evaluation.retrieval_eval import RetrievalResult, RetrievalRow
from vigie.evaluation.runner import confidence_intervals
from vigie.evaluation.thresholds import load_thresholds
from vigie.evaluation.tracking import local_artifact_location, log_report

path, run_name, *pairs = sys.argv[1:]
data = json.loads(Path(path).read_text(encoding="utf-8"))
rows = tuple(
    RetrievalRow(
        id=r["id"],
        expected=tuple(r["expected"]),
        retrieved=tuple(r["retrieved"]),
        recall_at_k=r["recall_at_k"],
        reciprocal_rank=r["reciprocal_rank"],
    )
    for r in data["rows"]
)
result = RetrievalResult(
    split=data["split"],
    k=data["k"],
    depth=data["depth"],
    questions=data["questions"],
    recall_at_k=data["recall_at_k"],
    mrr=data["mrr"],
    rows=rows,
)
settings = Settings()
config = dict(pair.split("=", 1) for pair in pairs)
config["source"] = f"vigie-eval retrieval --out {Path(path).name}"
report = {
    "split": result.split,
    "llm": "none",
    "config": config,
    "metrics": {"recall_at_k": result.recall_at_k, "mrr": result.mrr},
    "ci": confidence_intervals(result, None, load_thresholds(settings.thresholds_path)),
    "retrieval_rows": data["rows"],
}
client = open_client(settings.eval_tracking_uri)
location = local_artifact_location(settings.eval_tracking_uri, settings.eval_artifact_dir)
run_id = log_report(
    client, settings.eval_experiment, report, run_name=run_name, artifact_location=location
)
interval = report["ci"]["recall_at_k"]
print(
    f"{run_name}: recall@5 {result.recall_at_k:.4f} [{interval['low']:.4f}, "
    f"{interval['high']:.4f}], mrr {result.mrr:.4f}, mlflow run {run_id}"
)
