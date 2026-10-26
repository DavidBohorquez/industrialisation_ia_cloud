import pandas as pd

from livraison_express.abstractions.experiment_tracker import ExperimentTracker
from livraison_express.abstractions.model_repository import ModelRepository
from livraison_express.abstractions.order_data_source import OrderDataSource
from livraison_express.core.domain import TrainedModel
from livraison_express.core.training import run_training, train_model


class InMemoryOrderSource(OrderDataSource):
    def __init__(self, orders: pd.DataFrame):
        self._orders = orders

    def load_orders(self) -> pd.DataFrame:
        return self._orders


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
    dirty_orders = pd.concat([orders, orders.iloc[[0]]], ignore_index=True)
    repository = InMemoryModelRepository()
    tracker = RecordingTracker()

    model = run_training(
        InMemoryOrderSource(dirty_orders),
        repository,
        tracker,
        "2.0.0",
        random_state=0,
        evaluation_threshold=0.5,
    )

    assert repository.load("2.0.0") is model
    assert tracker.runs == [(model, {"random_state": 0})]
    metrics = model.card.metrics
    assert set(metrics) == {"accuracy", "precision", "recall", "f1_score", "roc_auc"}
    assert metrics["roc_auc"] > 0.7


def test_metrics_follow_the_evaluation_threshold(orders):
    lenient = train_model(orders, "a", random_state=0, evaluation_threshold=0.2).card.metrics
    strict = train_model(orders, "b", random_state=0, evaluation_threshold=0.8).card.metrics

    assert strict["precision"] > lenient["precision"]
    assert strict["recall"] < lenient["recall"]
    assert strict["roc_auc"] == lenient["roc_auc"]
