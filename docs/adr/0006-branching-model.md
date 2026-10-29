# ADR-0006: GitFlow branches, semantic versions and Docker image tags

- **Status:** Proposed
- **Date:** 2026-10-29

## Context

Session 3 of the course asks for GitFlow, Semantic Versioning, a changelog and a Docker image built by GitHub Actions on each release. The project is an HTTP API that we run ourselves: one version is live at a time, there is one maintainer, and there are no servers yet (no dev, staging or production machine). The code on `main` at `eaf5119` is the version that `pyproject.toml` calls `1.0.0`.

Two families of branching models were compared:

| | GitFlow | Trunk-based / GitHub Flow |
|---|---|---|
| Long-lived branches | `main`, `develop` | `main` |
| How a version is stabilised | a `release/*` branch that only receives fixes | the same image is promoted from staging to production; unfinished work is merged behind feature flags |
| Fits | several versions maintained at once (libraries, installed software), or a formal release freeze | one live version, continuous delivery, a preview environment per pull request |
| Cost | more merges; merging a release into `main` creates a new commit, so an image built from `main` is a rebuild, not the image that was tested | needs strong CI, feature flags and, ideally, preview environments |

## Decisions

1. **GitFlow branches.**
   - `main`: released code only. Every commit on `main` comes from a `release/*` or `hotfix/*` merge and carries a version tag.
   - `develop`: integration branch, created from `main` at `v1.0.0`.
   - `feature/<short-name>`: created from `develop`, merged back into `develop` through a pull request.
   - `release/<X.Y.Z>`: created from `develop` when the version's content is complete. It only receives fixes, the version bump and the changelog. Merged into `main` (then tagged) and back into `develop`.
   - `hotfix/<X.Y.Z>`: created from `main` for an urgent fix. Merged into `main` (then tagged) and back into `develop`.
2. **Merges keep history.** Pull requests are merged with a merge commit, never squashed or rebased for `release/*` and `hotfix/*`: `main` and `develop` must share those commits, otherwise the next release conflicts with changes both branches already contain.
3. **Semantic Versioning.** Tags are annotated and named `vX.Y.Z`. The `version` in `pyproject.toml` is changed on the release or hotfix branch so that it equals the tag. Release candidates are `X.Y.Z-rc.N`.
4. **The application version and the model version are independent.** The tag names the code; `MODEL_VERSION` (`artifacts/<version>/`, ADR-0000) names a trained model. A new model does not need a code release, and a code release does not need a new model.
5. **Docker image tags (ghcr.io) follow the branch that produced the image.**

   | Event | Image tags | Stands in for |
   |---|---|---|
   | tag `vX.Y.Z` on `main` | `X.Y.Z`, `X.Y`, `latest` | production |
   | push on `release/X.Y.Z` (optional) | `X.Y.Z-rc.<CI run number>` | staging |
   | push on `develop` (optional) | `dev` | development |
   | `feature/*` | none: CI tests only | local machine |

   Only the first row is required by the course.

## Consequences

- No work is committed directly on `main` or `develop`: every change goes through a `feature/*` branch and a pull request into `develop`, checked by CI once the workflow exists.
- A release takes six steps: `release/X.Y.Z` branch, version bump in `pyproject.toml`, changelog section, pull request into `main`, tag `vX.Y.Z`, merge back into `develop`.
- The `X.Y.Z` image is rebuilt from the merge commit on `main`. Its code equals the last release candidate, but it is not the same image (different digest). Promoting the tested image (re-tagging the last `-rc.N` as `X.Y.Z`) would close that gap; the rebuild is accepted for now because the course asks for a build on release.
- Docker tags only allow letters, digits, `_`, `.` and `-`. SemVer build metadata (`+20261026`) cannot be a tag; the commit and build date go into the image labels (`org.opencontainers.image.revision`, `org.opencontainers.image.created`).
- To revisit if the project becomes a continuously delivered service with real environments: move to trunk-based development (`main` and short feature branches, a preview environment per pull request, one image promoted from staging to production) and drop `develop` and `release/*`. GitFlow's author recommends this for continuously delivered web applications (note added in 2020 to "A successful Git branching model").
