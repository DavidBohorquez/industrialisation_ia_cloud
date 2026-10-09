import pandas as pd

from src.abstractions.model_repository import ModelRepository
from src.abstractions.order_data_source import OrderDataSource
from src.core.domain import TrainedModel
from src.core.training import run_training


class InMemoryOrderSource(OrderDataSource):
    def __init__(self, orders: pd.DataFrame):
        self._orders = orders

    def load_orders(self) -> pd.DataFrame:
        return self._orders


class InMemoryModelRepository(ModelRepository):
    def __init__(self):
        self.models: dict[str, TrainedModel] = {}

    def save(self, model: TrainedModel) -> None:
        self.models[model.version] = model

    def load(self, version: str) -> TrainedModel:
        return self.models[version]


def test_run_training_cleans_trains_and_saves(orders):
    dirty_orders = pd.concat([orders, orders.iloc[[0]]], ignore_index=True)
    repository = InMemoryModelRepository()

    model = run_training(InMemoryOrderSource(dirty_orders), repository, "2.0.0", random_state=0)

    assert repository.load("2.0.0") is model
    assert set(model.metrics) == {"accuracy", "precision", "recall", "f1_score", "roc_auc"}
    assert model.metrics["roc_auc"] > 0.7
