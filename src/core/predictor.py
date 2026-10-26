from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from src.core.domain import Factor, Prediction, TrainedModel
from src.core.explanation import linear_contributions

ELIGIBLE = "oui"
NOT_ELIGIBLE = "non"


class EligibilityPredictor:
    def __init__(self, model: TrainedModel, threshold: float = 0.5):
        if not 0 <= threshold <= 1:
            raise ValueError("Le seuil de décision doit être compris entre 0 et 1.")

        self._model = model
        self._threshold = threshold

    @property
    def model(self) -> TrainedModel:
        return self._model

    @property
    def threshold(self) -> float:
        return self._threshold

    def predict_one(self, order: Mapping[str, Any]) -> Prediction:
        return self.predict_many([order])[0]

    def predict_many(self, orders: Sequence[Mapping[str, Any]]) -> list[Prediction]:
        probabilities = self._probabilities(self._to_frame(orders))
        timestamp = datetime.now(timezone.utc).isoformat()

        return [
            Prediction(
                express_eligible=bool(probability >= self._threshold),
                decision=ELIGIBLE if probability >= self._threshold else NOT_ELIGIBLE,
                probability=round(float(probability), 4),
                model_version=self._model.version,
                prediction_timestamp=timestamp,
            )
            for probability in probabilities
        ]

    def predict_batch(self, orders: pd.DataFrame) -> pd.DataFrame:
        self._check_features(orders.columns)

        probabilities = self._probabilities(orders)
        eligible = probabilities >= self._threshold

        result = orders.copy()
        result["eligibility_probability"] = probabilities.round(4)
        result["express_eligible"] = eligible.astype(int)
        result["decision"] = np.where(eligible, ELIGIBLE, NOT_ELIGIBLE)
        result["model_version"] = self._model.version

        return result

    def top_factors(self, order: Mapping[str, Any], limit: int = 3) -> list[Factor]:
        factors = linear_contributions(self._model.pipeline, self._to_frame([order]))
        return factors[:limit]

    def _to_frame(self, orders: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
        for order in orders:
            self._check_features(order.keys())

        return pd.DataFrame(
            [{feature: order[feature] for feature in self._model.features} for order in orders]
        )

    def _check_features(self, available: Iterable[str]) -> None:
        missing_features = set(self._model.features) - set(available)

        if missing_features:
            raise ValueError(f"Variables manquantes : {sorted(missing_features)}")

    def _probabilities(self, data: pd.DataFrame) -> np.ndarray:
        return self._model.pipeline.predict_proba(data[self._model.features])[:, 1]
