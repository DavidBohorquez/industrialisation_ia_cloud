# ADR-0000: Where to store the model artifacts

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

The application must reload a trained model at startup without retraining on every deployment.
The model is a few MB, written rarely and read often.

## Options considered

| Option | Advantage | Drawback |
|---|---|---|
| A. Local directory | No service to install | No reliable versioning on its own |
| B. Network file system | Easy sharing between machines | Concurrent access is painful |
| C. Model registry (e.g. MLflow) | Native versioning | Extra service to maintain |

## Decision

Option A: `FileModelRepository` writes to `ARTIFACTS_DIR` (default `artifacts/`).
Likely move to option C at around 1M users.

## Consequences

- Every model version is explicit: one sub-folder per version (`artifacts/<version>/model.joblib` + `metadata.json`).
- A saved version is never overwritten; a new model needs a new `MODEL_VERSION`.
- The rest of the code depends only on the `ModelRepository` abstraction, so option C means adding one class under `src/infrastructure/` and one line in `src/factory.py`.
- When that happens, this ADR is marked "Superseded by ADR-000X".
