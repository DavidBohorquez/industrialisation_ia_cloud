# Contributing

Thank you for your interest in the project. This guide explains how to report a problem, set up the code and get a change merged. Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## Report a bug or suggest a change

- Open a [GitHub issue](https://github.com/DavidBohorquez/industrialisation_ia_cloud/issues/new/choose) with the bug report or feature request form. For a bug, give the application version (and the model version if relevant) and the exact steps to reproduce it.
- **Security vulnerabilities are never reported in a public issue**: follow [SECURITY.md](SECURITY.md).

## Set up the project

Requirements: Python 3.13+ and git. [uv](https://docs.astral.sh/uv/) is only needed to change a dependency.

```bash
git clone https://github.com/DavidBohorquez/industrialisation_ia_cloud.git
cd industrialisation_ia_cloud
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-train.lock -r requirements-dev.lock  # add -r requirements-notebook.lock for the notebook
pip install --no-deps -e .
ruff check . && pytest                                          # everything should pass before you start
```

## Branches and pull requests

The repository follows GitFlow ([ADR-0006](docs/adr/0006-branching-model.md)):

```
main      released versions only, one tag vX.Y.Z per merge
develop   integration of the next version (default branch)
feature/<short-name>    your work: from develop, back into develop through a pull request
release/<X.Y.Z>, hotfix/<X.Y.Z>    maintainers only (see "Releases" below)
```

1. Update `develop` and create your branch: `git switch develop && git pull --ff-only && git switch -c feature/<short-name>`.
2. Commit small, focused changes (see "Commit messages").
3. Push and open a pull request into **`develop`**, using the template.
4. The required checks must pass: `serving tests`, `training tests` and `lock files in sync`. Nobody can merge a pull request with a red check, nor push directly to `develop` or `main`.
5. The pull request is merged with **Create a merge commit** (never squashed), then the branch is deleted.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `type(optional scope): summary`, in English, imperative mood, 72 characters at most.

| Type | For | Example |
|---|---|---|
| `feat` | a new behaviour | `feat(api): split liveness and readiness health checks` |
| `fix` | a bug fix | `fix(cli): exit with code 1 on an invalid order file` |
| `refactor` | same behaviour, better code | `refactor: package the application as livraison_express` |
| `docs` | documentation, ADRs | `docs(adr): record the dependency management decision` |
| `test` | tests only | `test: cover the batch size limit` |
| `build` | packaging, dependencies, Docker | `build: split dependencies into a train extra...` |
| `ci` | GitHub Actions workflows | `ci: lint and test pull requests...` |
| `chore` | tooling and housekeeping | `chore: add ruff lint configuration` |

## Before opening a pull request

- [ ] `ruff check .` and `pytest` pass locally.
- [ ] New behaviour comes with tests. The tests must not need network access, real data or a trained model on disk (`tests/conftest.py` trains a small model in memory).
- [ ] [CHANGELOG.md](CHANGELOG.md) has a line under `## [Unreleased]` (Added, Changed, Fixed, Removed...).
- [ ] The README and the docs match the change. A significant decision (architecture, tool, process) gets an ADR in `docs/adr/`: copy the structure of the latest one (Status, Date, Context, Decisions, Consequences) with the next number.
- [ ] If the HTTP contract changed: `python -m livraison_express.api.export_openapi` regenerates `docs/openapi.json` (a test fails otherwise).

### Changing a dependency

Dependencies are managed as described in [ADR-0007](docs/adr/0007-dependency-management.md):

1. Edit the range in `pyproject.toml`: `[project] dependencies` for serving, the `train` extra for training, the `dev` or `notebook` group for tools.
2. Run `scripts/update-locks.sh`. To upgrade a package that is already locked, run `uv lock --upgrade-package <name>` first.
3. Commit `pyproject.toml`, `uv.lock` and the four `requirements*.lock` files together. The `lock files in sync` check fails otherwise.

Serving code (the API, the CLI and everything they import) must not import `mlflow`: `tests/test_dependency_boundary.py` and the `serving tests` job check it. Tests that need `mlflow` carry `pytestmark = pytest.mark.training` and import it inside the test.

## Code style

- `ruff check .` enforces the lint rules configured in `pyproject.toml`.
- Business code in `src/livraison_express/core/` depends only on the abstractions in `abstractions/`; concrete classes live in `infrastructure/` and are chosen in `factory.py` (see "Architecture" in the [README](README.md)). Pydantic stays in `api/`.
- Code, comments and documentation are in English. The CLI help texts and the original notebook are in French.

## Releases (maintainers)

1. `git switch develop && git pull --ff-only && git switch -c release/X.Y.Z`.
2. Set `version = "X.Y.Z"` in `pyproject.toml`, run `scripts/update-locks.sh` (the version is recorded in `uv.lock`), and move the `[Unreleased]` entries of `CHANGELOG.md` under `## [X.Y.Z] - YYYY-MM-DD`.
3. Open a pull request from `release/X.Y.Z` into `main`, merge it with a merge commit.
4. Tag the merge commit on `main` and push the tag: `git tag -a vX.Y.Z -m "Release X.Y.Z" && git push origin vX.Y.Z`. The release workflow publishes the Docker images.
5. Open a pull request from `main` into `develop` to bring the release commits back.
