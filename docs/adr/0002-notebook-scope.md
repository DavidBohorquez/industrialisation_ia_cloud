# ADR-0002: Which notebook code goes into the application

- **Status:** Accepted. The "model card" and "MLflow tracking" rows are superseded by [ADR-0004](0004-mlflow-tracking-and-model-card.md); the "pipeline/training" and "prediction" rows by [ADR-0005](0005-align-with-correction.md).
- **Date:** 2026-10-07

## Context

The notebook mixes code the final client needs (validation, cleaning, training, prediction) with exploration code that only helps the data scientist.

## Decision

| Notebook part | Destination |
|---|---|
| Data generation | `src/livraison_express/infrastructure/dev/synthetic_orders.py` (dev data source) |
| Quality checks and cleaning | `src/livraison_express/core/data_quality.py` |
| Feature lists and preprocessing | `src/livraison_express/core/features.py` |
| Pipeline, split, training, metrics | `src/livraison_express/core/training.py` |
| Threshold, single, batch and "real-time" prediction | `src/livraison_express/core/predictor.py` (one class, no duplicated logic) |
| Model saving and reloading | `ModelRepository` + `FileModelRepository` |
| Prediction tests and bad-data simulation | `tests/` |
| Example orders | `examples/` |
| Exploration (`describe`, plots), feature-importance plot, printed model card | Not ported; stays in the notebook |
| MLflow tracking | Not ported for now (planned for session 4) |

## Consequences

- The application only needs pandas, numpy, scikit-learn and joblib (`requirements.txt`). Notebook tools are in `requirements-dev.txt`.
- Metrics are saved in each model version's `metadata.json` instead of MLflow.
