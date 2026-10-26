from dataclasses import asdict, dataclass
from typing import Any, Protocol

import numpy as np
import pandas as pd


class Classifier(Protocol):
    def predict_proba(self, data: pd.DataFrame) -> np.ndarray: ...


@dataclass(frozen=True)
class ModelEntity:
    """Model card: what a trained model is, how it was evaluated and where it must not be trusted."""

    project: str
    model_version: str
    model_type: str
    task: str
    target: str
    features: list[str]
    metrics: dict[str, float]
    evaluation_threshold: float
    trained_at: str
    limitations: list[str]


@dataclass(frozen=True)
class TrainedModel:
    pipeline: Classifier
    card: ModelEntity


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
