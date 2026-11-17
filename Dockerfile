# syntax=docker/dockerfile:1
#
# Images of the express delivery eligibility service (ADR-0008).
#
#   docker build -t livraison-express .                           API (default: last stage)
#   docker build --target train -t livraison-express-train .      one-off training job
#   docker build --target test .                                  lint + tests inside the image
#
#              ┌─ build-serve ───────────────────────────► serve
#   base ──────┤      └─ build-train ─┬──────────────────► train
#                                     └─ test
#
# The final images (serve, train) only receive the virtual environment built in the build
# stages: no pip cache, no tests, no build tools.

# Pinned by digest (the tag can move, the digest cannot). Debian 13 slim, amd64 and arm64.
ARG PYTHON_IMAGE=python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

# ---------- base: shared by every stage ----------
FROM ${PYTHON_IMAGE} AS base

# PYTHONDONTWRITEBYTECODE: no .pyc written at run time (the API runs on a read-only filesystem).
# PYTHONUNBUFFERED: logs reach `docker logs` immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# Rootless: the processes run as "app" (uid 10001), never as root.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app

WORKDIR /app

# ---------- build-serve: dependencies of the API, then the package ----------
FROM base AS build-serve
RUN python -m venv /opt/venv

# Lock file first: this layer is rebuilt only when the dependencies change, not on every code change.
COPY requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.lock

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
# Regular install (not editable): the paths config.py would derive from the source tree are
# given by environment variables in the final stages instead.
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps .

# ---------- build-train: + the train extra (mlflow) ----------
# Same resolution as the serving lock (ADR-0007): the packages already installed are kept.
FROM build-serve AS build-train
COPY requirements-train.lock ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-train.lock

# ---------- test: the CI checks, run in the image's environment ----------
FROM build-train AS test
COPY requirements-dev.lock ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-dev.lock
COPY tests ./tests
COPY docs/openapi.json ./docs/openapi.json
# Editable here: a test reads docs/openapi.json through PROJECT_ROOT, which must be /app.
RUN pip install --no-deps -e . \
    && ruff check --no-cache . \
    && pytest -p no:cacheprovider

# ---------- train: one-off job, writes a model version into /app/artifacts ----------
FROM base AS train
COPY --from=build-train /opt/venv /opt/venv
ENV ARTIFACTS_DIR=/app/artifacts \
    MLFLOW_TRACKING_URI=sqlite:////app/mlruns/mlflow.db \
    MLFLOW_ARTIFACT_LOCATION=/app/mlruns
RUN mkdir -p /app/artifacts /app/mlruns && chown app:app /app/artifacts /app/mlruns
USER app
# docker run livraison-express-train            -> trains MODEL_VERSION
ENTRYPOINT ["python", "-m", "livraison_express"]
CMD ["train"]

# ---------- serve: the HTTP API (default target) ----------
FROM base AS serve
COPY --from=build-serve /opt/venv /opt/venv
ENV ARTIFACTS_DIR=/app/artifacts
RUN mkdir -p /app/artifacts && chown app:app /app/artifacts
USER app
# Only the API port. 0.0.0.0: listen on the container's network interface, not just its loopback.
EXPOSE 8000
# Liveness (ADR-0003): the process answers. Readiness (/health/ready) also needs a model.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --start-interval=2s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
# Other commands work too: docker run livraison-express predict --help
ENTRYPOINT ["python", "-m", "livraison_express"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
