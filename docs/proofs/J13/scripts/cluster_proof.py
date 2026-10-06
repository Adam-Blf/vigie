"""Collect the J13 evidence from the k3d dev cluster.

Usage: python cluster_proof.py <kubeconfig> <kubectl-argo-rollouts binary>
The Qdrant key is read from its Secret and only used in a request header, never printed.
"""

import base64
import subprocess
import sys
import time
import urllib.error
import urllib.request

KUBECONFIG, ROLLOUTS = sys.argv[1], sys.argv[2]
OBJECTS = "rollout,analysistemplate,hpa,traefikservice,ingressroute,middleware,networkpolicy"
OBJECTS += ",cronjob,job,pvc"


def k(*args: str) -> list[str]:
    return ["kubectl", "--kubeconfig", KUBECONFIG, *args]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603


def show(label: str, cmd: list[str]) -> None:
    done = run(cmd)
    print(f"$ {label}\n{done.stdout}{done.stderr}exit code: {done.returncode}\n")


def get(url: str, headers: dict[str, str] | None = None) -> str:
    request = urllib.request.Request(url, headers=headers or {})  # noqa: S310 - local http
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:  # noqa: S310
            names = ("X-Frame-Options", "X-Content-Type-Options", "Referrer-Policy")
            found = {name: resp.headers.get(name) for name in names if resp.headers.get(name)}
            return f"status {resp.status} {found}"
    except urllib.error.HTTPError as err:
        return f"status {err.code}"


show("kubectl version", k("version"))
show("kubectl get nodes -o wide", k("get", "nodes", "-o", "wide"))
show("kubectl get ns vigie --show-labels", k("get", "ns", "vigie", "--show-labels"))
show("kubectl get pods -A", k("get", "pods", "-A"))
show("kubectl -n vigie top pod", k("-n", "vigie", "top", "pod"))
show(f"kubectl -n vigie get {OBJECTS}", k("-n", "vigie", "get", OBJECTS))
rollout = [ROLLOUTS, "--kubeconfig", KUBECONFIG, "-n", "vigie", "get", "rollout", "vigie-api"]
show("kubectl argo rollouts get rollout vigie-api -n vigie", [*rollout, "--no-color"])
args_path = "jsonpath={.spec.template.spec.containers[0].args}"
show(
    "argo-rollouts controller args",
    k("-n", "argo-rollouts", "get", "deploy", "argo-rollouts", "-o", args_path),
)

# Denied flows must be refused; the allowed scrape shows the policies are not a blanket.
for pod, url in (
    ("deploy/vigie-web", "http://qdrant:6333/readyz"),
    ("deploy/vigie-web", "http://169.254.169.254/"),
    ("deploy/prometheus", "http://mlflow:5000/health"),
):
    probe = k("-n", "vigie", "exec", pod, "--", "wget", "-T", "4", "-qO-", url)
    show(f"{pod} -> {url} (expected refused)", probe)
promtool = ["promtool", "query", "instant", "http://localhost:9090", "up"]
show(
    "prometheus up series (allowed scrape)",
    k("-n", "vigie", "exec", "deploy/prometheus", "--", *promtool),
)

for path in ("/", "/v1/ask"):
    url = f"http://127.0.0.1:4780{path}"
    print(f"$ GET {url} through Traefik\n{get(url)}\n")

forward = k("-n", "vigie", "port-forward", "--address", "127.0.0.1", "svc/qdrant", "6733:6333")
tunnel = subprocess.Popen(forward, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603
time.sleep(6)
secret = k("-n", "vigie", "get", "secret", "vigie-secrets", "-o", "jsonpath={.data.qdrant-api-key}")
key = base64.b64decode(run(secret).stdout).decode()
print(f"$ GET qdrant /collections without api-key\n{get('http://127.0.0.1:6733/collections')}\n")
with_key = get("http://127.0.0.1:6733/collections", {"api-key": key})
print(f"$ GET qdrant /collections with api-key from the Secret\n{with_key}\n")
tunnel.terminate()

run(k("-n", "vigie", "delete", "job", "qdrant-snapshot-proof", "--ignore-not-found"))
show(
    "create job from cronjob/qdrant-snapshot",
    k("-n", "vigie", "create", "job", "--from=cronjob/qdrant-snapshot", "qdrant-snapshot-proof"),
)
complete = ["--for=condition=complete", "job/qdrant-snapshot-proof", "--timeout=240s"]
show("wait for completion", k("-n", "vigie", "wait", *complete))
show("snapshot job logs", k("-n", "vigie", "logs", "job/qdrant-snapshot-proof"))
