from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from src.core.domain import Prediction, TrainedModel

ELIGIBLE = "oui"
NOT_ELIGIBLE = "non"


class EligibilityPredictor:
    def __init__(self, model: TrainedModel, threshold: float = 0.5):
        if not 0 <= threshold <= 1:
            raise ValueError("Le seuil de décision doit être compris entre 0 et 1.")

        self._model = model
        self._threshold = threshold

    def predict_one(self, order: Mapping[str, Any]) -> Prediction:
        self._check_features(order.keys())

        input_df = pd.DataFrame([{feature: order[feature] for feature in self._model.features}])
        probability = float(self._probabilities(input_df)[0])
        eligible = probability >= self._threshold

        return Prediction(
            express_eligible=eligible,
            decision=ELIGIBLE if eligible else NOT_ELIGIBLE,
            probability=round(probability, 4),
            model_version=self._model.version,
            prediction_timestamp=datetime.now(timezone.utc).isoformat(),
        )

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

    def _check_features(self, available: Iterable[str]) -> None:
        missing_features = set(self._model.features) - set(available)

        if missing_features:
            raise ValueError(f"Variables manquantes : {sorted(missing_features)}")

    def _probabilities(self, data: pd.DataFrame) -> np.ndarray:
        return self._model.pipeline.predict_proba(data[self._model.features])[:, 1]
