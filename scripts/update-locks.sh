#!/usr/bin/env bash
# Regenerate uv.lock and the requirements*.lock files that pip installs from.
# Run it after changing a dependency in pyproject.toml, then commit every changed file.
# Needs uv (https://docs.astral.sh/uv/). CI fails when these files are out of date.
set -euo pipefail
cd "$(dirname "$0")/.."

# One resolution for every extra, group and platform: shared packages get the same version everywhere.
uv lock

# One file per install profile, exact versions and hashes. The project itself is installed
# separately with `pip install --no-deps -e .`.
export_lock() { uv export --frozen --no-emit-project --quiet "$@"; }
export_lock --no-default-groups --output-file requirements.lock                     # serving
export_lock --no-default-groups --extra train --output-file requirements-train.lock # training
export_lock --only-group dev --output-file requirements-dev.lock                    # tests, lint
export_lock --only-group notebook --output-file requirements-notebook.lock          # notebook
