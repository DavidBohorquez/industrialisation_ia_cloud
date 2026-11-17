# ADR-0008: One Dockerfile for the train and serve images, the model in a volume

- **Status:** Accepted
- **Date:** 2026-11-17

## Context

The course asks for a Dockerfile and a `docker-compose.yml`, with an optimised and secured image. The project runs two different jobs (ADR-0007): the API, which needs the serving dependencies only, and the training job, which also needs `mlflow`. The API needs a model that the training job produces; models are git-ignored (`artifacts/`) and must not live in the repository. `config.py` derives its default paths (`artifacts/`, `.env`, MLflow storage) from the source tree, which is only right when the package is installed in editable mode.

## Decisions

1. **One multi-stage Dockerfile, three targets.** `serve` (the default, last stage) and `train` are the images people run; `test` installs the dev tools and runs `ruff` and `pytest` inside the image environment. The final stages start again from the base image and copy only the virtual environment (`/opt/venv`) built in a build stage: no pip cache, no tests, no build tools.
2. **Base image `python:3.13-slim-trixie`, pinned by digest.** Debian slim rather than Alpine: the scientific wheels (numpy, pandas, scikit-learn, scipy) target glibc, and on Alpine (musl) pip may have to compile them. The digest makes builds reproducible; moving to a newer base image is a deliberate change of one line.
3. **The model is not baked into an image.** The training image writes `MODEL_VERSION` into a volume mounted at `/app/artifacts`; the serving image reads it, read-only. Code and model versions stay independent (ADR-0006).
   Rejected: training during `docker build` (every code change retrains, and the model is tied to the image) and downloading the model at start-up (needs a model registry; a later step).
4. **Regular install, paths from the environment.** The images install the package without `-e` and set `ARTIFACTS_DIR` (and, for training, `MLFLOW_TRACKING_URI` and `MLFLOW_ARTIFACT_LOCATION`) with `ENV`. No `.env` file is ever copied: `.dockerignore` is an allow-list, so only the files the Dockerfile needs reach the builder.
5. **Security.** The processes run as a non-root user (uid 10001). Only port 8000 is exposed, with a `HEALTHCHECK` on `/health` (liveness, ADR-0003). `docker-compose.yml` runs the API with a read-only root filesystem, the model volume read-only, all Linux capabilities dropped, `no-new-privileges`, and its port bound to `127.0.0.1`. Settings are passed as environment variables at run time.
6. **Build speed and size.** Lock files are copied and installed before the code, so a code change does not reinstall the dependencies; pip's cache is a BuildKit cache mount, outside the image layers.
7. **CI job `docker image`.** On every pull request it builds the `test` target, builds both images, trains a model into a volume, starts the API with `docker compose up --wait` and calls `/health/ready` and `POST /v1/predictions`.

## Consequences

- Measured on a developer machine: the serving image is about 160 MB compressed (about 0.5 GB unpacked, most of it scipy, pandas, numpy and scikit-learn, which the model needs) and contains no `mlflow`; the training image is about 290 MB compressed.
- A model version is trained once with `docker compose run --rm train`; training refuses a version that already exists.
- Running the serving image alone needs a model mounted at `/app/artifacts`; without one, the API starts and `/health/ready` returns 503 (ADR-0003).
- The image tags of ADR-0006 are applied by the release workflow when a version tag is pushed.
