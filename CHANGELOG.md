# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). These are application versions; model versions (`MODEL_VERSION`) change independently ([ADR-0006](docs/adr/0006-branching-model.md)).

## [Unreleased]

### Added

- Continuous integration (GitHub Actions) on every pull request and merge into `develop` and `main`: ruff, then pytest once per install profile (serving without MLflow, training with it), and a check that the lock files match `pyproject.toml`.
- Lock files with exact versions and hashes for each install profile (`requirements.lock`, `requirements-train.lock`, `requirements-dev.lock`, `requirements-notebook.lock`), generated from `uv.lock` by `scripts/update-locks.sh`.
- A `train` extra for MLflow, and `dev` and `notebook` dependency groups.
- A test that fails if the API or the CLI imports MLflow.
- Docker: one multi-stage `Dockerfile` with `serve` (API), `train` and `test` targets, rootless and read-only containers, and a `docker-compose.yml` where the training job writes a model into a volume that the API reads. A CI job builds the images, trains a model and calls the API.
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

[Unreleased]: https://github.com/DavidBohorquez/industrialisation_ia_cloud/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/DavidBohorquez/industrialisation_ia_cloud/releases/tag/v1.0.0
