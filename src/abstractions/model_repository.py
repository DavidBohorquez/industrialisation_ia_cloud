from abc import ABC, abstractmethod

from src.core.domain import TrainedModel


class ModelRepository(ABC):
    @abstractmethod
    def save(self, model: TrainedModel) -> None: ...

    @abstractmethod
    def load(self, version: str) -> TrainedModel: ...
