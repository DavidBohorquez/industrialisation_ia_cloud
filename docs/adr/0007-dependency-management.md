# ADR-0007: Dependency ranges, a train extra, dev/notebook groups and lock files

- **Status:** Accepted
- **Date:** 2026-11-16
- **Supersedes:** the dependency notes of ADR-0002 (`requirements.txt` / `requirements-dev.txt`) and ADR-0004 (`mlflow` in `requirements.txt`)

## Context

Dependencies were pinned in two files: `requirements.txt` (the application, including `mlflow`) and `requirements-dev.txt` (test tools, plus unpinned notebook tools). Every environment installed everything: CI downloaded jupyter, and a serving image would have carried `mlflow` and what it pulls in (Flask, SQLAlchemy, pyarrow...) although the API never imports it (`factory.py` imports the MLflow tracker only for training). Only direct dependencies were pinned, so their own dependencies could change from one install to the next.

The project now has several install profiles: the serving image, the training job, CI and a developer laptop with the notebook. The serving image will load models that the training job saved with joblib, so both must run the same scikit-learn.

## Decisions

1. **Ranges in `pyproject.toml`, exact versions in a lock.** Direct dependencies are listed inline with compatible ranges: lower bound = version tested, upper bound = next version allowed to break the code (next major, or next minor for `0.x` packages). `scikit-learn` is bounded to its minor version (`>=1.9,<1.10`) because a pickled model is only guaranteed to load with the version that saved it.
2. **Each dependency goes where its users are.**

   | Kind | Section | Contents | Why there |
   |---|---|---|---|
   | Base | `[project] dependencies` | FastAPI, uvicorn, pandas, scikit-learn... | what serving needs: API, CLI, predictions |
   | Extra `train` | `[project.optional-dependencies]` | `mlflow` | an optional feature of the package for its users (the `train` command) |
   | Groups `dev`, `notebook` | `[dependency-groups]` (PEP 735) | pytest, ruff, httpx2 / jupyter, matplotlib, seaborn | tools for people working on the repository, not part of the installed package |

3. **uv generates, pip installs.** `uv lock` resolves every extra, group and platform at once into `uv.lock`: a package shared by two profiles gets the same version in both, valid on macOS and Linux. `scripts/update-locks.sh` exports one hashed file per profile: `requirements.lock` (serving), `requirements-train.lock` (serving + `train`), `requirements-dev.lock` and `requirements-notebook.lock`. Every environment installs with `pip install -r <profile>.lock [-r requirements-dev.lock]`, then `pip install --no-deps -e .`: `--no-deps` stops pip from resolving again, so nothing outside the lock comes in, and the hashes make pip refuse a downloaded file that differs from the locked one.
   Rejected: `pip-compile` (pip-tools), which resolves each file separately (a shared package can get different versions in two profiles) and for the machine it runs on (macOS), while CI and Docker run Linux.
4. **CI tests each profile.** The `tests` job runs as a matrix: `serving tests` installs `requirements.lock` only and runs `pytest -m "not training"`; `training tests` adds the `train` extra and runs every test. Tests that need `mlflow` carry the `training` marker and import it inside the test, because pytest imports every test file before filtering by marker. `tests/test_dependency_boundary.py` imports the API and the CLI in a fresh interpreter and fails if `mlflow` is loaded. `lock files in sync` regenerates the locks and fails on any difference. The three checks are required on `develop` and `main` (ADR-0006).

## Consequences

- Changing a dependency: edit `pyproject.toml`, run `scripts/update-locks.sh` (needs [uv](https://docs.astral.sh/uv/)), then commit `pyproject.toml`, `uv.lock` and the four `requirements*.lock` files together. CI goes red otherwise.
- `uv lock` keeps the locked versions while they satisfy the ranges, so a new release on PyPI never changes the locks by itself. Upgrades are deliberate (`uv lock --upgrade-package <name>`, then the script) and arrive in a pull request where CI shows their effect: the first lock moved pandas from 3.0.6 to 3.1.0, whose deprecation of `Series.dt.dayofweek` was fixed in the same change.
- The serving profile has 32 packages and no `mlflow`; the training profile has 95. Serving code that imports `mlflow`, or a package only `mlflow` brings in, turns `serving tests` red before it can break an image.
- The package is installed in editable mode in CI and on laptops: `config.py` derives `PROJECT_ROOT` (and so `docs/openapi.json`, `artifacts/`, `.env`) from its own location, which only points to the repository when the code runs from `src/`. Docker images will install `requirements.lock` (serving) or `requirements-train.lock` (training) without `-e`, so the Docker change must resolve those paths another way.
- The notebook is kept as received (ADR-0002): its own `%pip install` cell installs unpinned packages, outside the lock. The `notebook` group only provides Jupyter and the plotting libraries for running it locally.
