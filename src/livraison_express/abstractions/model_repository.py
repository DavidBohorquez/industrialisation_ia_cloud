from abc import ABC, abstractmethod

from livraison_express.core.domain import TrainedModel


class ModelRepository(ABC):
    @abstractmethod
    def save(self, model: TrainedModel) -> None: ...

    @abstractmethod
    def load(self, version: str) -> TrainedModel: ...
