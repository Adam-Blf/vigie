"""Command line entry: `python -m vigie.deploy rendered.yaml [more.yaml ...]`.

Pass the output of `kustomize build` for every layer that lands on the node (the
application overlay and the cluster add-ons). The budget is computed on all of them
together, the hardening rules only on the application namespace, since the add-on
controllers legitimately need their service account token.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from vigie.config import get_settings
from vigie.deploy.budget import Budget, Report, compute
from vigie.deploy.manifests import load_documents, workloads
from vigie.deploy.policy import check_all, image_problems


def _read(source: str) -> str:
    return sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")


def _render(report: Report) -> str:
    named = [
        (f"{line.workload.namespace}/{line.workload.kind}/{line.workload.name}", line)
        for line in sorted(report.lines, key=lambda item: -item.request_mib)
    ]
    width = max([len(label) for label, _ in named] + [len("k3s system reserve")]) + 2
    rows = [f"{'workload':<{width}}{'pods':>5}{'req Mi':>9}{'lim Mi':>9}{'cpu m':>8}"]
    for label, line in named:
        rows.append(
            f"{label:<{width}}{line.workload.pods:>5}{line.request_mib:>9}"
            f"{line.limit_mib:>9}{line.cpu_request_m:>8}"
        )
    b = report.budget
    rows.append(f"{'k3s system reserve':<{width}}{'':>5}{b.system_reserve_mib:>9}")
    rows.append(
        f"{'total':<{width}}{'':>5}{report.requests_mib:>9}{report.limits_mib:>9}"
        f"{report.cpu_requests_m:>8}"
    )
    rows.append(f"{'budget':<{width}}{'':>5}{b.requests_mib:>9}{b.limits_mib:>9}")
    rows[-1] += f"{b.cpu_requests_m:>8}"
    return "\n".join(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vigie.deploy", description=__doc__)
    parser.add_argument("sources", nargs="+", help="rendered manifests, or - for stdin")
    parser.add_argument("--policy-namespace", default="vigie")
    args = parser.parse_args(argv)

    docs = [doc for source in args.sources for doc in load_documents(_read(source))]
    found = workloads(docs)
    settings = get_settings()
    budget = Budget(
        requests_mib=settings.k8s_requests_budget_mib,
        limits_mib=settings.k8s_limits_budget_mib,
        cpu_requests_m=settings.k8s_cpu_requests_budget_m,
        system_reserve_mib=settings.k8s_system_reserve_mib,
    )
    report = compute(found, budget)
    print(_render(report))

    own = [w for w in found if w.namespace == args.policy_namespace]
    failures = report.violations() + check_all(own) + image_problems(own)
    for failure in failures:
        print(f"FAIL {failure}")
    print("OK" if not failures else f"{len(failures)} problem(s)")
    return 1 if failures else 0
