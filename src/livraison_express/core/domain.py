from dataclasses import asdict, dataclass
from typing import Any, Protocol

import numpy as np
import pandas as pd


class Classifier(Protocol):
    def predict_proba(self, data: pd.DataFrame) -> np.ndarray: ...


@dataclass(frozen=True)
class TrainedModel:
    pipeline: Classifier
    version: str
    features: list[str]
    metrics: dict[str, float]
    trained_at: str


@dataclass(frozen=True)
class Prediction:
    express_eligible: bool
    decision: str
    probability: float
    model_version: str
    prediction_timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Factor:
    """Contribution d'une variable à la décision, par rapport à une commande moyenne."""

    feature: str
    contribution: float
