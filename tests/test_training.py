import pytest

from livraison_express.abstractions.experiment_tracker import ExperimentTracker
from livraison_express.abstractions.model_repository import ModelRepository
from livraison_express.core.domain import TrainedModel
from livraison_express.core.features import TARGET_COLUMN
from livraison_express.core.learning.ml_trainer import MLTrainer
from livraison_express.core.training import run_training
from livraison_express.infrastructure.dev.in_memory_order_repository import (
    InMemoryOrderRepository,
)


class InMemoryModelRepository(ModelRepository):
    def __init__(self):
        self.models: dict[str, TrainedModel] = {}

    def save(self, model: TrainedModel) -> None:
        self.models[model.card.model_version] = model

    def load(self, version: str) -> TrainedModel:
        return self.models[version]


class RecordingTracker(ExperimentTracker):
    def __init__(self):
        self.runs: list[tuple[TrainedModel, dict]] = []

    def log_training(self, model: TrainedModel, params) -> str:
        self.runs.append((model, dict(params)))
        return "run-1"


def test_run_training_cleans_trains_saves_and_tracks(orders):
    records = orders.to_dict(orient="records")
    records[5] = {**records[5], "carrier_capacity": 3}
    model_repository = InMemoryModelRepository()
    tracker = RecordingTracker()

    model = run_training(
        InMemoryOrderRepository(records),
        model_repository,
        tracker,
        MLTrainer(random_state=0, evaluation_threshold=0.5),
        "2.0.0",
    )

    assert model_repository.load("2.0.0") is model
    assert tracker.runs == [(model, {"random_state": 0, "test_size": 0.20})]
    metrics = model.card.metrics
    assert set(metrics) == {"accuracy", "precision", "recall", "f1_score", "roc_auc"}
    assert metrics["roc_auc"] > 0.7


def test_orders_without_outcome_are_not_used_for_training(orders):
    records = orders.to_dict(orient="records")
    unlabelled = {**records[0], "order_id": "CMD-NEW", TARGET_COLUMN: None}
    order_repository = InMemoryOrderRepository([*records, unlabelled])

    assert len(order_repository.get_training_data()) == len(records)


def test_training_without_labelled_orders_fails_clearly():
    with pytest.raises(ValueError, match="résultat connu"):
        run_training(
            InMemoryOrderRepository(),
            InMemoryModelRepository(),
            RecordingTracker(),
            MLTrainer(random_state=0, evaluation_threshold=0.5),
            "2.0.0",
        )
