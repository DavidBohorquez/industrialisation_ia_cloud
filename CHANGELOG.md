# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). These are application versions; model versions (`MODEL_VERSION`) change independently ([ADR-0006](docs/adr/0006-branching-model.md)).

## [Unreleased]

### Added

- `erp-simulator/`: the course ERP simulator (TP4) that fills PostgreSQL and MongoDB, with the fixes it needed to build and start (listed in its README).
- `erp-simulator/src/erp_simulator/outcome.py`: simulates the `express_eligible` outcome with the course heuristic, translated to the ERP's values (assumptions in the simulator's README). Its tests run with the rest of the suite.
- The ERP simulator writes `express_eligible` into PostgreSQL and MongoDB, revealed `LABEL_DELAY_DAYS` simulated days (default 2) after each order, and resumes its simulated clock after a restart ([ADR-0010](docs/adr/0010-labels-in-the-erp-simulator.md)).
- A read-only PostgreSQL role `ml_reader` for the application, created by the simulator's init script.
- `erp-simulator/docker-compose.replica.yml`: a read-only PostgreSQL replica (streaming hot standby, cloned with `pg_basebackup`) for the data team, added on top of `docker-compose.erp.yml`. On the shared `livraison-net` network it answers as `erp-postgres`, and the production primary is kept off that network.
- ADR-0009: orders are read from PostgreSQL (full history) with a read-only role on a streaming replica, never on the production primary; MongoDB is the fallback if neither can be obtained.
- Training and the command line (`predict`, `predict-batch`) reject category values outside the vocabulary with a message listing the allowed ones. Before, the model's encoder ignored them silently and scored the order as if the field were missing.
- Training can read the labelled orders of the ERP's PostgreSQL database: `ORDER_SOURCE=postgres` with `POSTGRES_DSN`. `PostgresOrderReader` cannot write (no `save` method, read-only connection, read-only role), and `erp_order_mapper.py` translates each row into the application's vocabulary; rows it cannot translate are skipped and counted in a warning.
- `OrderReader` and `OrderWriter` interfaces; `OrderRepository` combines them for stores the application owns.
- `psycopg[binary]` dependency (PostgreSQL driver), imported only when `ORDER_SOURCE=postgres`.
- Tests marked `postgres`, skipped unless `TEST_POSTGRES_DSN` is set, and a CI job `postgres tests` that runs them against a PostgreSQL 17 service container.
- ADR-0012 (read-only `OrderReader`) and ADR-0013 (one setting per dependency).
- `docker-compose.test.yml`: the whole chain with fake ERP data (simulator, PostgreSQL primary and replica, MongoDB, training job reading the replica as `ml_reader`, API on port 8001).
- `docker-compose.prod.yml` and `.env.prod.example`: the released images only, training from the company's read replica (`POSTGRES_DSN`), resource limits and log rotation; required settings fail fast.
- Airflow orchestration of the retraining (`orchestration/airflow/`): the official Airflow 3.4.0 compose file (CeleryExecutor), with its changes listed in its header, and the DAG `retrain_express_model`. Every 10 minutes it counts the labelled orders on the ERP read replica and, once at least 1000 new ones have arrived since the last training, runs the training image with the `DockerOperator` to train a new version `<prefix>+<run date and time>` (default prefix `2.0.0`). Promoting that version to the API stays manual.
- ADR-0014 (orchestrate retraining with Airflow).

### Changed

- **BREAKING:** order categories use the application's canonical vocabulary, adjusted so that every data source, starting with the ERP, can be translated into it ([ADR-0011](docs/adr/0011-canonical-vocabulary-and-source-adapters.md)). The HTTP contract (`API_VERSION`, `docs/openapi.json`) is now 2.0.0; routes keep the `/v1` prefix. A request with a removed value gets a `422` listing the allowed values. Migration for API clients:

  | Field | Old value | New value |
  |---|---|---|
  | `weather` | `normal`, `pluie`, `neige`, `orage` | unchanged, and `vent` is new (strong wind without a storm) |
  | `delivery_zone` | `proche_banlieue` | `banlieue` |
  | `delivery_zone` | `centre`, `banlieue`, `rurale` | unchanged (`banlieue` now covers every suburb) |
  | `customer_type` | `standard`, `premium` | `particulier` (individual) or `professionnel` (business). No automatic mapping: a service tier does not say what the customer is. |

- **BREAKING:** the default `MODEL_VERSION` is 2.0.0 (`config.py`, `.env.example`, `docker-compose.yml`), so that this version never loads a model trained on the old vocabulary (1.0.0). Train 2.0.0 before serving: `python -m livraison_express train` or `docker compose run --rm train`.
- The dev order generator uses the canonical values with the ERP simulator's penalties (`vent` 0.20, `banlieue` 0.175, `professionnel` +0.15). Numeric distributions and the scoring formula are unchanged; the notebook keeps the original vocabulary.
- README: `docker compose up -d --wait api` returns once the API is healthy, and the `docker run` instructions show how to wait for the `(healthy)` status before calling the API.
- `run_training` takes an `OrderReader`; `factory.build_order_repository` is now `build_order_reader`.
- `get_all` and `get_training_data` return orders sorted by `order_id` in every store, so the same orders always give the same training set.
- `ORDER_SOURCE=postgres` without `POSTGRES_DSN` stops the program at startup with a clear message.

### Removed

- The `APP_ENV` setting: each dependency now has its own setting (ADR-0013). An `APP_ENV` left in a `.env` file is ignored.

## [1.1.0] - 2026-11-17

### Added

- Continuous integration (GitHub Actions) on every pull request and merge into `develop` and `main`: ruff, then pytest once per install profile (serving without MLflow, training with it), and a check that the lock files match `pyproject.toml`.
- Lock files with exact versions and hashes for each install profile (`requirements.lock`, `requirements-train.lock`, `requirements-dev.lock`, `requirements-notebook.lock`), generated from `uv.lock` by `scripts/update-locks.sh`.
- A `train` extra for MLflow, and `dev` and `notebook` dependency groups.
- A test that fails if the API or the CLI imports MLflow.
- Docker: one multi-stage `Dockerfile` with `serve` (API), `train` and `test` targets, rootless and read-only containers, and a `docker-compose.yml` where the training job writes a model into a volume that the API reads. A CI job builds the images, trains a model and calls the API.
- Release workflow: pushing a tag `vX.Y.Z` on `main` publishes the `serve` and `train` images on `ghcr.io` (`linux/amd64` and `linux/arm64`, tags `X.Y.Z`, `X.Y` and `latest`) and creates the GitHub release from this changelog.
- Collaboration files: MIT license, contributing guide, security policy, code of conduct, issue and pull request templates, and this changelog.
- ADR-0006 (branching and versioning), ADR-0007 (dependency management) and ADR-0008 (Docker images).

### Changed

- Dependencies are declared in `pyproject.toml` with compatible ranges. Install with `pip install -r <profile>.lock`, then `pip install --no-deps -e .`.
- pandas 3.1.0 (was 3.0.6) and the latest compatible patch releases of the other dependencies.

### Removed

- `requirements.txt` and `requirements-dev.txt`, replaced by the lock files.

## [1.0.0] - 2026-10-29

### Added

- Command line: `train`, `predict`, `predict-batch` and `serve`.
- HTTP API (FastAPI) with an OpenAPI contract, liveness and readiness checks, and a template explanation of each decision.
- Settings from environment variables and `.env` (pydantic-settings), and logging.
- MLflow experiment tracking, and a model card stored with each model version.

[Unreleased]: https://github.com/DavidBohorquez/industrialisation_ia_cloud/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/DavidBohorquez/industrialisation_ia_cloud/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/DavidBohorquez/industrialisation_ia_cloud/releases/tag/v1.0.0
