from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from livraison_express.core.domain import TrainedModel


class ExperimentTracker(ABC):
    @abstractmethod
    def log_training(self, model: TrainedModel, params: Mapping[str, Any]) -> str:
        """Record one training run (parameters, metrics, model) and return its run id."""
