# Express Delivery Eligibility

[![CI](https://github.com/DavidBohorquez/industrialisation_ia_cloud/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/DavidBohorquez/industrialisation_ia_cloud/actions/workflows/ci.yml)

Predicts whether an order can be delivered express (same day), as a decision aid alongside business rules.

This project turns an experimental Jupyter notebook into a production-ready Python application. It is the practical work for the course *Industrialisation de l'IA dans le cloud* (YNOV Toulouse, M2 Data & IA).

## Problem

| | |
|---|---|
| Task | Binary classification |
| Target | `express_eligible` (1 = eligible, 0 = not eligible) |
| Model | Logistic regression (scikit-learn pipeline) |
| Data | Generated orders (default), or the company's ERP database read-only (`ORDER_SOURCE=postgres`) |

Features used by the model:

- **Order:** `hour`, `day_of_week`, `weekend`, `order_value_eur`, `weight_kg`, `customer_type`
- **Logistics:** `distance_km`, `delivery_zone`, `carrier_capacity`, `weather`
- **Warehouse:** `stock_available`, `preparation_time_min`

Categories use the application's own vocabulary; each data source is translated into it by an adapter ([ADR-0011](docs/adr/0011-canonical-vocabulary-and-source-adapters.md)):

| Feature | Allowed values |
|---|---|
| `weather` | `normal`, `pluie`, `neige`, `orage` (storm), `vent` (strong wind, no storm) |
| `delivery_zone` | `centre`, `banlieue` (any suburb), `rurale` |
| `customer_type` | `particulier` (individual, B2C), `professionnel` (business, B2B) |

## Getting started

Requirements: Python 3.13+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-train.lock -r requirements-dev.lock  # app, training and test tools
pip install --no-deps -e .             # the livraison_express package, editable
python -m livraison_express train      # train model MODEL_VERSION (needed once)
```

Add `-r requirements-notebook.lock` to the first `pip install` to run the notebook.

### Dependencies

`pyproject.toml` lists compatible version ranges. The `*.lock` files, generated from `uv.lock`, pin the exact versions (with hashes) that every environment installs, one file per install profile:

| File | Contents | Used by |
|---|---|---|
| `requirements.lock` | API, CLI, predictions, PostgreSQL driver | serving |
| `requirements-train.lock` | serving + `train` extra (MLflow) | training job |
| `requirements-dev.lock` | `dev` group: pytest, ruff, httpx2 | tests and lint |
| `requirements-notebook.lock` | `notebook` group: jupyter, matplotlib, seaborn | notebook |

To change a dependency, edit `pyproject.toml`, run `scripts/update-locks.sh` (needs [uv](https://docs.astral.sh/uv/)) and commit `pyproject.toml`, `uv.lock` and the `*.lock` files together. CI fails when they are out of sync.

## HTTP API

```bash
python -m livraison_express serve                        # http://127.0.0.1:8000 (--host, --port)
uvicorn livraison_express.api.main:app --reload          # during development: restarts on file changes
```

- Swagger UI (try the endpoints in the browser): http://127.0.0.1:8000/docs
- OpenAPI contract: http://127.0.0.1:8000/openapi.json, with a committed copy in [`docs/openapi.json`](docs/openapi.json)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/predictions` | One order -> prediction + explanation (`?explain=false` to skip it) |
| `POST` | `/v1/predictions/batch` | `{"orders": [...]}`, up to 1000 orders (`?explain=true` to add explanations) |
| `GET` | `/v1/model` | Loaded model: version, training date, threshold, features, metrics |
| `GET` | `/health` | Liveness: always `200` while the process runs |
| `GET` | `/health/ready` | Readiness: `200` when a model is loaded, `503` otherwise |

Example:

```bash
curl -X POST http://127.0.0.1:8000/v1/predictions \
     -H "Content-Type: application/json" -d @examples/order.json
```

```json
{
  "express_eligible": true,
  "decision": "oui",
  "probability": 0.932,
  "model_version": "2.0.0",
  "prediction_timestamp": "2026-11-20T17:26:06.836102+00:00",
  "explanation": {
    "text": "Cette commande est éligible à la livraison express (probabilité estimée : 93 %). Ce qui joue en sa faveur : la distance (3,5 km), la capacité du transporteur (0,85) et la zone de livraison (centre).",
    "source": "template",
    "top_factors": ["distance_km", "carrier_capacity", "delivery_zone"]
  }
}
```

The explanation text is generated from the model's exact contributions by a template today (`"source": "template"`). An LLM generator can replace it later without changing this contract (see ADR-0003).

Errors:

| Code | When | Body |
|---|---|---|
| `422` | Missing field, value out of range, unknown category or field, `weekend` inconsistent with `day_of_week` | Every problem at once, with field, received value and rule |
| `413` | Batch over 1000 orders | `Batch limited to 1000 orders (received N).` |
| `503` | No model loaded | `Prediction service temporarily unavailable: no model is loaded.` |
| `500` | Unexpected error | Generic message + `reference`; details only in server logs |

## Command line

```bash
python -m livraison_express serve                                        # start the HTTP API
python -m livraison_express train                                        # train and save model MODEL_VERSION
ORDER_SOURCE=postgres POSTGRES_DSN=postgresql://ml_reader:...@erp-postgres:5432/livraison_express \
  python -m livraison_express train                                      # train on the ERP's labelled orders
python -m livraison_express predict examples/order.json                  # one order -> JSON result
python -m livraison_express predict-batch examples/orders.csv out.csv    # CSV of orders -> CSV with predictions
python -m livraison_express.api.export_openapi                           # regenerate docs/openapi.json
python -m pytest                                                         # run the tests
TEST_POSTGRES_DSN=postgresql://postgres:test@127.0.0.1:55440/livraison_express \
  python -m pytest -m postgres                                           # PostgreSQL tests (see below)
ruff check .                                                             # lint (rules in pyproject.toml)
```

## Run with Docker

Two images built from one `Dockerfile` ([ADR-0008](docs/adr/0008-docker-images.md)): `train` writes a model into a volume, `serve` (the API) reads it.

```bash
docker compose run --rm train      # train MODEL_VERSION into the "models" volume (once per version)
docker compose up -d --wait api    # API on http://127.0.0.1:8000 (Swagger UI: /docs), returns once healthy
docker compose logs -f api         # follow the logs
docker compose down                # stop (add --volumes to delete the models and MLflow runs)
docker build --target test .       # run lint and tests inside the image
```

```
                 docker compose run --rm train          docker compose up -d --wait api
                 ┌──────────────────────────┐           ┌──────────────────────────┐
                 │ train image (+ mlflow)   │  writes   │ serve image (no mlflow)  │──► 127.0.0.1:8000
                 │ python -m ... train      │ ───────►  │ python -m ... serve      │
                 └──────────────────────────┘ "models"  └──────────────────────────┘
                                               volume      reads it read-only
```

- **Settings** come from environment variables, e.g. `MODEL_VERSION=2.1.0 docker compose run --rm train`. Compose also reads a `.env` file next to `docker-compose.yml`; no `.env` is ever copied into an image.
- **Security:** the containers run as a non-root user (uid 10001); the API has a read-only filesystem, a read-only model volume, no Linux capabilities, and only port 8000, published on `127.0.0.1`.
- **Size:** the serving image is about 160 MB compressed (most of it scipy, pandas, numpy and scikit-learn). The final images only receive the virtual environment built in earlier stages: no pip cache, tests or build tools.
- The CI job `docker image` runs these same steps on every pull request.

### Environments: local, test, production

| File | Orders come from | Images | Use |
|---|---|---|---|
| `docker-compose.yml` | generated in memory (`ORDER_SOURCE=memory`) | built locally | develop, CI |
| `docker-compose.test.yml` | the ERP simulator's PostgreSQL **read replica** (`ml_reader`) | built locally | test the whole chain with fake ERP data |
| `docker-compose.prod.yml` | the company's read replica, `POSTGRES_DSN` from `.env.prod` | released on ghcr.io | production |

```
 test:   ERP simulator ──> PostgreSQL primary ──streaming──> replica (erp-postgres) ──ml_reader──> train ──> models ──> api :8001
 prod:   company ERP ───> PostgreSQL primary ──────────────> replica ─────────── POSTGRES_DSN ──> train ──> models ──> api :8000
```

Test environment, step by step:

```bash
docker network create livraison-net                                   # once (shared with Airflow)
docker compose -f docker-compose.test.yml up -d --build --wait postgres postgres-replica mongodb
docker compose -f docker-compose.test.yml up -d erp-simulator         # history, then a live batch every 5 s
docker compose -f docker-compose.test.yml run --rm train              # trains MODEL_VERSION on labelled ERP orders
docker compose -f docker-compose.test.yml up -d --wait api            # http://127.0.0.1:8001/docs
docker compose -f docker-compose.test.yml --profile train down -v     # delete everything
```

Production: `cp .env.prod.example .env.prod`, fill it in, then `docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm train` and `... up -d --wait api`. Nothing is built and no database runs there; missing settings stop Compose with a message.

### Published images

Pushing a version tag `vX.Y.Z` on `main` runs `.github/workflows/release.yml`: it checks that the tag matches `pyproject.toml` and `CHANGELOG.md`, publishes both images on GitHub Container Registry for `linux/amd64` and `linux/arm64` (Apple Silicon), then creates the GitHub release with the changelog section.

| Image | Tags |
|---|---|
| `ghcr.io/davidbohorquez/industrialisation_ia_cloud` (API) | `X.Y.Z`, `X.Y`, `latest` |
| `ghcr.io/davidbohorquez/industrialisation_ia_cloud-train` (training job) | `X.Y.Z`, `X.Y`, `latest` |

Run a released version without the source code:

```bash
docker volume create models
docker run --rm -v models:/app/artifacts ghcr.io/davidbohorquez/industrialisation_ia_cloud-train:1.1.0
docker run -d --name livraison-api -p 127.0.0.1:8000:8000 -v models:/app/artifacts:ro --read-only \
  ghcr.io/davidbohorquez/industrialisation_ia_cloud:1.1.0
docker ps --filter name=livraison-api   # wait until STATUS shows "(healthy)" instead of "(health: starting)"
curl http://127.0.0.1:8000/health/ready
```

The API needs a few seconds to start: until `docker ps` shows `(healthy)`, a request can get an empty reply (`curl: (52)`). The image's `HEALTHCHECK` calls `/health` every 2 seconds while the container starts. In a script, wait for it instead of retrying:

```bash
until [ "$(docker inspect --format '{{.State.Health.Status}}' livraison-api)" = healthy ]; do sleep 1; done
```

## Configuration

Settings are read by `src/livraison_express/config.py` (`pydantic-settings`), in this priority order: environment variables, then a `.env` file at the project root, then the defaults below. Copy `.env.example` to `.env` to change them locally. Invalid values (e.g. `DECISION_THRESHOLD=abc`, or `ORDER_SOURCE=postgres` without `POSTGRES_DSN`) stop the program at startup with a clear message.

Each dependency has its own setting, not one environment name for all of them ([ADR-0013](docs/adr/0013-per-dependency-settings.md)): the training job can read the ERP while the API, in the same environment, reads no orders.

| Variable | Default | Meaning |
|---|---|---|
| `ORDER_SOURCE` | `memory` | Where jobs read orders from: `memory` (generated) or `postgres` (the ERP database, read-only) |
| `POSTGRES_DSN` | none | Required when `ORDER_SOURCE=postgres`: `postgresql://<user>:<password>@<host>:5432/<database>`, with the read-only role. A secret: never logged, never committed |
| `ARTIFACTS_DIR` | `<project>/artifacts` | Where model versions are stored |
| `MODEL_VERSION` | `2.0.0` | Version to train (must be new) or to load |
| `DECISION_THRESHOLD` | `0.5` | Probability from which an order is eligible (0 to 1) |
| `RANDOM_STATE` | `42` | Seed for data generation, split and model |
| `LOG_LEVEL` | `INFO` | Minimum level of log messages shown: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `MLFLOW_TRACKING_URI` | `sqlite:///<project>/mlflow.db` | Where training runs are recorded (`mlflow ui --backend-store-uri sqlite:///mlflow.db`) |
| `MLFLOW_ARTIFACT_LOCATION` | `<project>/mlruns` | Where MLflow stores run files (model, model card) |

### Reading orders from the ERP (PostgreSQL)

With `ORDER_SOURCE=postgres`, the training job reads the labelled orders (`express_eligible` not NULL) of the ERP's `public.orders` table through `PostgresOrderReader` ([ADR-0012](docs/adr/0012-read-only-order-reader.md)). It can only read: the class has no `save` method, its connection runs every transaction `READ ONLY`, and the DSN names the read-only role `ml_reader`. Each row is translated into the application's vocabulary by `erp_order_mapper.py` (`rain` -> `pluie`, `suburb` -> `banlieue`, capacity in slots out of 50 -> share between 0 and 1...). A row with a value the mapper does not know is skipped and counted in a warning.

The tests marked `postgres` need a throwaway server; they are skipped when `TEST_POSTGRES_DSN` is not set. Each test creates its own schema and drops it afterwards:

```bash
docker run -d --name pgtest -e POSTGRES_PASSWORD=test -e POSTGRES_DB=livraison_express -p 127.0.0.1:55440:5432 postgres:17-alpine
TEST_POSTGRES_DSN=postgresql://postgres:test@127.0.0.1:55440/livraison_express python -m pytest -m postgres
docker rm -f pgtest
```

## Project structure

```
.
├── pyproject.toml                    # package definition, dependency ranges (pip install --no-deps -e .)
├── uv.lock                           # exact versions of every dependency (generated)
├── requirements*.lock                # one install profile per file (generated from uv.lock)
├── scripts/update-locks.sh           # regenerates uv.lock and the requirements*.lock files
├── .github/workflows/ci.yml          # CI: lint, tests per install profile, lock files check, images
├── .github/workflows/release.yml     # on a version tag: publish the images, create the release
├── .github/ISSUE_TEMPLATE/           # bug report and feature request forms (+ pull_request_template.md)
├── CONTRIBUTING.md                   # how to report, set up, branch, commit and release
├── SECURITY.md                       # supported versions, private vulnerability reporting
├── CODE_OF_CONDUCT.md                # community rules (Contributor Covenant 3.0)
├── CHANGELOG.md                      # notable changes per version (Keep a Changelog)
├── LICENSE                           # MIT
├── Dockerfile                        # multi-stage: test, train and serve images
├── .dockerignore                     # allow-list of the files the images may contain
├── docker-compose.yml                # train job + API sharing a model volume
├── erp-simulator/                    # course ERP simulator (TP4): fills PostgreSQL and MongoDB
├── src/livraison_express/
│   ├── __main__.py                   # entry point: python -m livraison_express
│   ├── cli.py                        # commands serve / train / predict / predict-batch
│   ├── config.py                     # settings: environment variables, .env, defaults
│   ├── logging_config.py             # LOG_LEVEL and log format
│   ├── factory.py                    # picks the implementation for each abstraction (from settings)
│   ├── api/
│   │   ├── app.py                    # FastAPI endpoints and error handling
│   │   ├── schemas.py                # Pydantic models = OpenAPI contract
│   │   ├── main.py                   # app instance for uvicorn
│   │   └── export_openapi.py         # writes docs/openapi.json
│   ├── abstractions/
│   │   ├── model_repository.py       # ModelRepository (ABC)
│   │   ├── order_repository.py       # OrderReader, OrderWriter, OrderRepository (ABCs): orders as dicts
│   │   ├── explanation_generator.py  # ExplanationGenerator (ABC)
│   │   └── experiment_tracker.py     # ExperimentTracker (ABC)
│   ├── core/
│   │   ├── domain.py                 # TrainedModel, ModelEntity (model card), Prediction, Factor
│   │   ├── features.py               # feature contract: lists and allowed categories
│   │   ├── data_quality.py           # validation and cleaning
│   │   ├── training.py               # run_training: the training job (data -> save -> track)
│   │   ├── explanation.py            # contributions + TemplateExplanationGenerator
│   │   └── learning/
│   │       ├── ml_pipeline.py            # MLPipeline: preprocessing + logistic regression
│   │       ├── train_test_splitter.py    # TrainTestSplitter: stratified 80/20 split
│   │       ├── ml_trainer.py             # MLTrainer: fit, evaluate, model card
│   │       └── ml_predict.py             # MLPredict: probability -> decision
│   └── infrastructure/
│       ├── mlflow_tracking.py        # MlflowExperimentTracker (any environment)
│       ├── dev/
│       │   ├── order_generator.py            # generate_orders(): synthetic labelled orders
│       │   ├── in_memory_order_repository.py # InMemoryOrderRepository (read + write)
│       │   └── file_model_repository.py      # FileModelRepository
│       └── postgres/
│           ├── erp_order_mapper.py           # ERP row -> canonical order (anti-corruption layer)
│           └── postgres_order_reader.py      # PostgresOrderReader: reads the ERP, cannot write
├── tests/
├── examples/                         # sample inputs
├── docs/
│   ├── adr/                          # architecture decision records
│   └── openapi.json                  # API contract (generated)
└── notebooks/                        # original experiment (reference only)
```

## Architecture

Business code (`core/`) depends only on abstractions. Entry points (CLI, API) and the implementations in `infrastructure/` are connected in one place, `factory.py`, which picks each implementation from its own setting (dependency inversion, the "D" in SOLID). Code that only reads orders, like training, receives an `OrderReader`: it cannot write, whatever the source (interface segregation, the "I").

```
  terminal ──> cli.py ───────┐
                             ├──> factory.py ──> core/ (learning/, training, explanation)
  HTTP ──────> api/ ─────────┘                      │
               (Pydantic, OpenAPI)                  v
                                       abstractions/ (ABC contracts)
                                                    ^
                                                    │ implemented by
    infrastructure/ (dev/, postgres/, mlflow_tracking.py)  +  core/explanation.py (template)
```

Decisions are recorded in `docs/adr/`:

- [ADR-0000](docs/adr/0000-model-artifact-storage.md): model artifacts in a local directory, one folder per version
- [ADR-0001](docs/adr/0001-order-data-source.md): training data source abstracted per environment (superseded by ADR-0005 and ADR-0013)
- [ADR-0002](docs/adr/0002-notebook-scope.md): which notebook code goes into the application
- [ADR-0003](docs/adr/0003-http-api.md): HTTP API, OpenAPI contract and explanations
- [ADR-0004](docs/adr/0004-mlflow-tracking-and-model-card.md): MLflow experiment tracking and model card
- [ADR-0005](docs/adr/0005-align-with-correction.md): orders as dicts in an `OrderRepository`, learning classes aligned with the course correction
- [ADR-0006](docs/adr/0006-branching-model.md): GitFlow branches, semantic version tags and Docker image tags
- [ADR-0007](docs/adr/0007-dependency-management.md): dependency ranges, `train` extra, dev/notebook groups, `uv.lock` exported to one lock file per install profile, CI per profile
- [ADR-0008](docs/adr/0008-docker-images.md): one multi-stage Dockerfile for the train and serve images, the model in a volume, rootless and read-only containers
- [ADR-0009](docs/adr/0009-read-orders-from-postgres-replica.md): orders read from PostgreSQL (full history) through a read-only role on a streaming replica, never the production primary; MongoDB as fallback
- [ADR-0010](docs/adr/0010-labels-in-the-erp-simulator.md): the order outcome (`express_eligible`) simulated in the ERP simulator with the course heuristic, revealed after a simulated delay
- [ADR-0011](docs/adr/0011-canonical-vocabulary-and-source-adapters.md): the application's own category vocabulary, adjusted so every source maps into it, and one adapter per source in `infrastructure/`
- [ADR-0012](docs/adr/0012-read-only-order-reader.md): `OrderReader` and `OrderWriter` split; `PostgresOrderReader` reads the ERP and cannot write (no `save`, read-only connection and role)
- [ADR-0013](docs/adr/0013-per-dependency-settings.md): one setting per dependency (`ORDER_SOURCE`, `POSTGRES_DSN`) instead of the `APP_ENV` profile

## Status

- [x] Experimental notebook
- [x] Project structure
- [x] Notebook logic moved into `src/`
- [x] Model repository (abstraction + local file implementation)
- [x] Tests
- [x] Prediction API with OpenAPI contract
- [x] Template explanation (LLM-ready abstraction)
- [x] Model card and MLflow experiment tracking
- [ ] LLM explanation generator
- [x] Continuous integration (GitHub Actions) and locked dependencies
- [x] Collaboration files: license, contributing guide, security policy, code of conduct, changelog
- [x] Docker images (test, train, serve) and docker-compose
- [x] Release pipeline (images published on each version tag)
- [x] ERP data source (PostgreSQL read replica) and test / production compose files

## Limitations

- The dataset is synthetic; performance on real data may differ.
- The model is a decision aid and must not replace business rules.
- Explanations describe each feature's effect compared with an average order; they explain the model, not the real-world cause.

## Contributing

Bug reports, ideas and pull requests are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md) for the setup, the branching model and the checks a pull request must pass. Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md). Notable changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Security

Report vulnerabilities privately, never in a public issue: see [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE): you may use, copy, modify and distribute the code, including commercially, as long as the copyright and license notice stay with it. It comes without warranty.
