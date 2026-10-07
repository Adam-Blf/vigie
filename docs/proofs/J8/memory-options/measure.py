"""Memory of one API container after a warm-up, for docs/memory-options.md.

    python docs/proofs/J8/memory-options/measure.py <label> <container> <port> [extra...]

Waits for /healthz, issues a throwaway token inside the container (never printed), sends
the 20 questions of docs/proofs/J8/eval/pod_rss.py through POST /v1/ask (fake LLM), then
reads, in this order: `docker stats --no-stream` of the API container and of every extra
container named after it, the cgroup files memory.current, memory.peak and memory.stat
(anon, file) and VmRSS / VmHWM of PID 1. memory.peak counts the page cache of the model
files read at start; VmHWM is the high-water mark of the process alone. A second pass of
the same 20 questions, after the memory reads, gives the warm latency. Standard library
only, so it runs with any Python on the host. No question of the sealed test split.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request

QUESTIONS = [
    "Quelles obligations DORA impose-t-il pour le registre des prestataires tiers ?",
    "Which AI systems are prohibited under the AI Act?",
    "Quel délai pour notifier une violation de données personnelles ?",
    "Qui supervise la lutte contre le blanchiment selon l'AMLR ?",
    "What must a financial entity test in its digital operational resilience programme?",
] * 4


def sh(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout  # noqa: S603


def wait_healthy(base: str, limit_s: int = 600) -> float:
    start = time.perf_counter()
    while time.perf_counter() - start < limit_s:
        try:
            with urllib.request.urlopen(f"{base}/readyz", timeout=3) as r:  # noqa: S310
                if r.status == 200:
                    return time.perf_counter() - start
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1)
    raise SystemExit("api never became ready")


def token(container: str) -> str:
    out = sh("docker", "exec", container, "python", "-m", "vigie.api.tokens", "create", "mem")
    lines = [ln.strip() for ln in out.splitlines() if ln.strip() and "=" not in ln]
    return lines[-1]


def ask(base: str, secret: str, question: str) -> tuple[int, float]:
    body = json.dumps({"question": question}).encode()
    request = urllib.request.Request(  # noqa: S310 - local URL
        f"{base}/v1/ask",
        data=body,
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
    )
    begin = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as r:  # noqa: S310
            r.read()
            status = r.status
    except urllib.error.HTTPError as error:
        status = error.code
    return status, (time.perf_counter() - begin) * 1000


def cgroup(container: str) -> dict[str, int]:
    read = "cat /sys/fs/cgroup/memory.current /sys/fs/cgroup/memory.peak"
    current, peak = sh("docker", "exec", container, "sh", "-c", read).split()
    stat = dict(
        line.split()
        for line in sh("docker", "exec", container, "cat", "/sys/fs/cgroup/memory.stat")
        .strip()
        .splitlines()
    )
    status = sh("docker", "exec", container, "cat", "/proc/1/status")
    vm = {
        line.split(":")[0]: int(line.split()[1]) * (1 if line[0] == "T" else 1024)
        for line in status.splitlines()
        if line.startswith(("VmRSS", "VmHWM", "Threads"))
    }
    return {
        "current": int(current),
        "peak": int(peak),
        "anon": int(stat["anon"]),
        "file": int(stat["file"]),
        **vm,
    }


def mib(value: int) -> str:
    return f"{value / 2**20:.0f} MiB"


def main() -> int:
    label, container, port, *extra = sys.argv[1:]
    base = f"http://127.0.0.1:{port}"
    ready_s = wait_healthy(base)
    secret = token(container)
    results = [ask(base, secret, q) for q in QUESTIONS]
    statuses = sorted({s for s, _ in results})
    latencies = sorted(ms for _, ms in results)
    stats = sh(
        "docker",
        "stats",
        "--no-stream",
        "--format",
        "{{.Name}} {{.MemUsage}}",
        container,
        *extra,
    )
    print(f"## {label}")
    print(f"ready after {ready_s:.0f} s; statuses {statuses} over {len(results)} asks")
    p95 = latencies[int(0.95 * len(latencies)) - 1]
    print(
        f"POST /v1/ask median {statistics.median(latencies):.0f} ms, p95 {p95:.0f} ms "
        "(fake LLM, first ask included)"
    )
    memory = [(name, cgroup(name)) for name in (container, *extra)]
    # A second pass, models warm, for the latency only: memory was read before it.
    warm = sorted(ask(base, secret, q)[1] for q in QUESTIONS)
    p95_warm = warm[int(0.95 * len(warm)) - 1]
    print(
        f"POST /v1/ask warm pass: median {statistics.median(warm):.0f} ms, "
        f"p95 {p95_warm:.0f} ms over {len(warm)} asks"
    )
    print("docker stats --no-stream (after the first 20 asks):")
    for line in stats.strip().splitlines():
        print(f"  {line}")
    for name, c in memory:
        print(
            f"  {name}: cgroup current {mib(c['current'])}, peak {mib(c['peak'])}, "
            f"anon {mib(c['anon'])}, file {mib(c['file'])}; "
            f"PID 1 VmRSS {mib(c['VmRSS'])}, VmHWM {mib(c['VmHWM'])}, {c['Threads']} threads"
        )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
