# syntax=docker/dockerfile:1.12
# The Vigie API image, also used by the one-shot ingestion job (vigie-ingest, vigie-index).
#
#   docker build -f deploy/docker/api.Dockerfile -t vigie-api:dev .
#
# Stages: the locked dependencies, the models (downloaded and quantized at build time,
# with network), and a slim runtime that carries neither uv nor torch nor the build-only
# tools. The runtime stage then loads every model again as the non-root user with no
# network at all, so an image that would need the internet to answer is never produced.
# Base images are pinned by multi-architecture index digest: amd64 and arm64 (Oracle Ampere).

ARG PYTHON_IMAGE=docker.io/library/python:3.12-slim-bookworm@sha256:7753c33391fc9f01d1984375bf375eb6686d52ba10db6043a86634a5ccf90dcf

# uv is copied straight from its pinned image in both stages that need it. A FROM stage
# holding only uv, with --platform=$BUILDPLATFORM, crashed the dockerfile:1.12 frontend.
FROM ${PYTHON_IMAGE} AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.32@sha256:df4cae8f3a96d175e2e5f992e597550000edbe78fdc2594d5cd8de1a217f504c /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
# Dependencies first, in their own layer: a code change does not reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-editable
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable

# Build-only stages: the guard-model extra (huggingface-hub, onnx) never reaches the runtime.
# They run on the builder's own platform: ONNX files are the same for amd64 and arm64, and
# quantizing under QEMU took more than 20 minutes on its own. The runtime stage still loads
# every model on the target platform, so a model arm64 could not run fails the build there.
FROM --platform=$BUILDPLATFORM ${PYTHON_IMAGE} AS models
COPY --from=ghcr.io/astral-sh/uv:0.11.32@sha256:df4cae8f3a96d175e2e5f992e597550000edbe78fdc2594d5cd8de1a217f504c /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-editable --extra guard-model
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --extra guard-model
# Downloads go through cache mounts so a code change does not fetch a gigabyte again;
# only the copies under /opt/models end up in the image. Which models: the settings say,
# read from config.py at build time, so nothing here names one.
ENV PATH=/opt/venv/bin:$PATH \
    HF_HOME=/cache/hf \
    VIGIE_GUARD_MODEL_DIR=/opt/models/guard \
    VIGIE_EMBEDDING_CACHE_DIR=/cache/fastembed
# fastembed 0.8 lists two files for BM25 that the Qdrant/bm25 repository does not hold:
# the placeholder "mock.file" and the Tamil stop words. Online it never checks them, but
# its offline lookup requires every listed file, so the offline check below would fail
# on BM25 alone. Empty placeholders, created only when missing, satisfy it; the French
# stop words the index uses are the real ones.
RUN --mount=type=cache,target=/cache \
    python -m vigie.guard.prepare \
    && python -m vigie.deploy.models \
    && for snapshot in /cache/fastembed/models--Qdrant--bm25/snapshots/*/; do \
         for name in mock.file tamil.txt; do \
           [ -e "${snapshot}${name}" ] || : > "${snapshot}${name}"; \
         done; \
       done \
    && cp -a /cache/fastembed /opt/models/fastembed

FROM ${PYTHON_IMAGE} AS runtime
# Same uid and gid as the pod securityContext of deploy/k8s. /data belongs to that user so
# a fresh Docker volume mounted there starts with the right owner.
RUN groupadd --system --gid 10001 vigie \
    && useradd --system --uid 10001 --gid vigie --no-create-home \
       --home-dir /nonexistent --shell /usr/sbin/nologin vigie \
    && install -d -o 10001 -g 10001 -m 0750 /data
# Models first: they change far less often than the code, so this layer stays cached.
COPY --from=models /opt/models /opt/models
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
# The ingestion job checks downloads against the lock and builds the drift reference from
# the golden questions; both files are read-only inputs.
COPY data/corpus.lock data/corpus.lock
COPY data/golden/questions.jsonl data/golden/questions.jsonl
# Everything written at runtime goes to /data (a volume) or /tmp (a tmpfs), so the
# container runs with a read-only root filesystem.
# MALLOC_TRIM_THRESHOLD_: loading the guard classifier leaves about 270 MiB of freed
# memory that glibc keeps by default; a fixed 128 KiB threshold hands it back to the OS
# (measured in docs/proofs/J7/08-api-memory-by-model.txt).
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MALLOC_TRIM_THRESHOLD_=131072 \
    HF_HUB_OFFLINE=1 \
    HF_HOME=/tmp/hf \
    FASTEMBED_CACHE_PATH=/opt/models/fastembed \
    VIGIE_EMBEDDING_CACHE_DIR=/opt/models/fastembed \
    VIGIE_GUARD_MODEL_DIR=/opt/models/guard \
    VIGIE_HOST=0.0.0.0 \
    VIGIE_PORT=8710 \
    VIGIE_DATA_DIR=/data \
    VIGIE_CORPUS_DIR=/data/corpus \
    VIGIE_CORPUS_CACHE_DIR=/tmp/vigie-cache \
    VIGIE_CORPUS_LOCK_PATH=/app/data/corpus.lock \
    VIGIE_DB_PATH=/data/vigie.sqlite3 \
    VIGIE_AUDIT_DIR=/data/audit \
    VIGIE_DRIFT_REFERENCE_PATH=/data/drift/reference.npy \
    VIGIE_DRIFT_ANCHORS_PATH=/data/drift/anchors.npy
USER 10001:10001
# The offline load test of brief 11.11: non-root, no network, every model answers once.
RUN --network=none python -m vigie.deploy.models
EXPOSE 8710
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8710/healthz', timeout=4)"]
CMD ["python", "-m", "vigie.api"]
