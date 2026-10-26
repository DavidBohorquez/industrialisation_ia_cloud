from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from livraison_express.core.domain import Factor, Prediction


class ExplanationGenerator(ABC):
    source: str

    @abstractmethod
    def explain(
        self,
        prediction: Prediction,
        factors: list[Factor],
        order: Mapping[str, Any],
    ) -> str: ...
