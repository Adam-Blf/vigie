"""Run the canary AnalysisTemplate queries through promtool inside the Prometheus pod.

Usage: python promql_check.py <kubeconfig> <pod-template-hash>
A syntax error makes promtool exit non-zero; an empty vector means "inconclusive".
"""

import subprocess
import sys
from pathlib import Path

import yaml

kubeconfig, pod_hash = sys.argv[1], sys.argv[2]
rendered = Path("build/k8s/overlays-dev.yaml").read_text(encoding="utf-8")
template = next(d for d in yaml.safe_load_all(rendered) if d and d["kind"] == "AnalysisTemplate")
args = {a["name"]: a.get("value") for a in template["spec"]["args"]}
args |= {"canary-hash": pod_hash, "stable-hash": pod_hash}
for metric in template["spec"]["metrics"]:
    query = metric["provider"]["prometheus"]["query"]
    for name, value in args.items():
        query = query.replace(f"{{{{args.{name}}}}}", str(value))
    cmd = ["kubectl", "--kubeconfig", kubeconfig, "-n", "vigie", "exec", "deploy/prometheus"]
    cmd += ["--", "promtool", "query", "instant", "http://localhost:9090", query]
    done = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    result = done.stdout.strip() or "(empty vector: inconclusive)"
    print(f"== {metric['name']} promtool rc={done.returncode}\nquery:\n{query}")
    print(f"result: {result} {done.stderr.strip()}\n")
