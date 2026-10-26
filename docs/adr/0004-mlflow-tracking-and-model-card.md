# ADR-0004: MLflow experiment tracking and model card

- **Status:** Accepted
- **Date:** 2026-10-26
- **Supersedes:** the "model card" and "MLflow tracking" rows of ADR-0002

## Context

The professor's correction (`livraison_express_lite`) tracks every training in MLflow and stores a model card (`ModelEntity`) with the artifact. ADR-0002 had deferred both. Two constraints:

- MLflow is an external system (a database + an artifact store), and takes about 2 s to import with many dependencies. The API does not train, so it must not depend on it.
- In MLflow 3.17, the default tracking store is `sqlite:///mlflow.db` and the default artifact folder is `./mlruns`, both relative to the **current directory**.

## Decision

1. **`ModelEntity` (model card)** in `core/domain.py`: project, version, model type, task, target, features, metrics, evaluation threshold, training date, limitations. `TrainedModel` = pipeline + card. `FileModelRepository` writes the card as `metadata.json`; it stays the source of truth for serving (ADR-0000).
2. **Metrics are computed at the configured decision threshold**, recorded as `evaluation_threshold`. Precision, recall, F1 and accuracy depend on the threshold; ROC AUC does not.
3. **`ExperimentTracker` abstraction** (`abstractions/`) with `MlflowExperimentTracker` (`infrastructure/mlflow_tracking.py`, not `dev/`: the same class will target an MLflow server later). `run_training` receives it, like the repository; core never imports MLflow.
4. **Explicit locations**: `MLFLOW_TRACKING_URI` (default `<project>/mlflow.db`) and `MLFLOW_ARTIFACT_LOCATION` (default `<project>/mlruns`), set when the experiment is first created.
5. **`factory.build_experiment_tracker` imports MLflow lazily**, so starting the API does not load it.
6. **`skops_trusted_types=["numpy.dtype"]`**: MLflow 3.17 serializes scikit-learn models with skops, which only reloads allow-listed types. The pipeline's OneHotEncoder stores a `numpy.dtype` (a data-type descriptor, no code), so it is safe to trust.

## Consequences

- Order of a training run: train → save to the model repository → log to MLflow. If MLflow fails, the model is already saved and the command exits with an error.
- `mlflow` moves from `requirements-dev.txt` to `requirements.txt`.
- `metadata.json` changed format: models trained before this ADR must be retrained.
- `mlflow ui --backend-store-uri sqlite:///mlflow.db` shows the runs.
