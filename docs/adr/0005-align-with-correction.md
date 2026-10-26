# ADR-0005: Align training and prediction with the course correction

- **Status:** Accepted
- **Date:** 2026-10-26
- **Supersedes:** ADR-0001, and the "pipeline/training" and "prediction" rows of ADR-0002

## Context

The professor's correction (`livraison_express_lite`) splits machine learning into small classes, `MLPipeline`, `TrainTestSplitter`, `MLTrainer` and `MLPredict`, under `core/learning/`, and stores orders behind an `OrderRepository`. Our code had the same steps as functions (`build_pipeline`, `train_model`, `evaluate`), one class (`EligibilityPredictor`) and a read-only `OrderDataSource`. Using the course's names makes the project easier to compare with the reference and to grade.

## Decision: orders

1. **Orders are plain dicts** in the core, validated by Pydantic (`OrderRequest`) at the API boundary. No `OrderEntity` dataclass: the API already guarantees field names, types and ranges, and the learning code works on tables (pandas), so dicts avoid a conversion layer.
2. **`OrderRepository`** (`abstractions/order_repository.py`) replaces `OrderDataSource`: `save`, `get`, `get_all`, `count`, and `get_training_data` (orders whose outcome is known). Unlike the correction, `get_training_data` is part of the contract, so any implementation can be used for training (Liskov substitution).
3. **Dev implementation:** `InMemoryOrderRepository`, filled by `order_generator.generate_orders()` (notebook cell 8, returns dicts).
4. **The API does not store incoming orders yet.** Saving every client order is a new behaviour with privacy consequences; it needs its own decision.

## Decision: learning classes

| Correction | Ours now | Responsibility |
|---|---|---|
| `MLPipeline` | `core/learning/ml_pipeline.py` | Build a new, untrained pipeline (preprocessing + logistic regression) |
| `TrainTestSplitter` | `core/learning/train_test_splitter.py` | Stratified 80/20 split, features and target separated |
| `MLTrainer` | `core/learning/ml_trainer.py` | Split, fit, evaluate at the evaluation threshold, write the model card |
| `MLPredict` | `core/learning/ml_predict.py` (was `EligibilityPredictor`) | Probability → decision, single and batch, explanation factors |
| `Core.train_model` | `core/training.py` `run_training` | The training job: data → quality checks → `MLTrainer` → model repository → tracker |

Kept from our version (stronger, see the comparison):

- `MLTrainer` builds its own `MLPipeline` and `TrainTestSplitter`: they have one implementation each, so they are not injected (YAGNI). Abstractions (repositories, tracker) are injected.
- MLflow stays behind `ExperimentTracker` and is called by `run_training` **after** the model is saved (ADR-0004), not inside `MLTrainer`. A run is never recorded for a model that could not be stored, and `MLTrainer` stays a pure computation that tests can run without MLflow.
- No settings are read inside these classes: `factory.build_trainer` and `factory.build_predictor` pass them in.
- `factory.py` remains the composition root (no `Core` singleton).
- Abstractions stay in `abstractions/`, not `infrastructure/`: the contract belongs to the code that uses it (core), and some implementations are not infrastructure (`TemplateExplanationGenerator` lives in core).

## Consequences

- `features.py` keeps only the feature contract; the preprocessing moved into `MLPipeline`.
- Tests cover each class on its own (`tests/test_learning.py`, `tests/test_ml_predict.py`), and `tests/test_order_repository.py` holds contract tests that every future `OrderRepository` implementation must pass.
- A production order store (PostgreSQL, ERP...) means one new class under `infrastructure/` and one branch in `factory.build_order_repository`.
- The HTTP routes are unchanged (`/v1/predictions`).
