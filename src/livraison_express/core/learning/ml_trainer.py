from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

from livraison_express.core.domain import ModelEntity, TrainedModel
from livraison_express.core.features import FEATURE_COLUMNS, TARGET_COLUMN
from livraison_express.core.learning.ml_pipeline import MLPipeline
from livraison_express.core.learning.train_test_splitter import TrainTestSplitter

PROJECT_NAME = "eligibilite-livraison-express"

LIMITATIONS = (
    "Le jeu de données d'entraînement est synthétique.",
    "La décision ne doit pas être utilisée sans validation des règles métier.",
    "Les performances peuvent varier sur des données réelles.",
    "Le modèle ne remplace pas une analyse des contraintes opérationnelles.",
)


class MLTrainer:
    """Splits labelled orders, fits a new pipeline, evaluates it and writes its model card."""

    def __init__(self, random_state: int, evaluation_threshold: float, test_size: float = 0.20):
        self._pipeline = MLPipeline(random_state)
        self._splitter = TrainTestSplitter(random_state, test_size)
        self._evaluation_threshold = evaluation_threshold

    @property
    def params(self) -> dict[str, Any]:
        return {"random_state": self._splitter.random_state, "test_size": self._splitter.test_size}

    def train(self, orders: pd.DataFrame, version: str) -> TrainedModel:
        X_train, X_test, y_train, y_test = self._splitter.split(orders)

        pipeline = self._pipeline.get_model_pipeline()
        pipeline.fit(X_train, y_train)

        card = ModelEntity(
            project=PROJECT_NAME,
            model_version=version,
            model_type=type(pipeline.named_steps["classifier"]).__name__,
            task="classification binaire",
            target=TARGET_COLUMN,
            features=list(FEATURE_COLUMNS),
            metrics=self._evaluate(pipeline, X_test, y_test),
            evaluation_threshold=self._evaluation_threshold,
            trained_at=datetime.now(timezone.utc).isoformat(),
            limitations=list(LIMITATIONS),
        )
        return TrainedModel(pipeline=pipeline, card=card)

    def _evaluate(
        self, pipeline: Pipeline, X_test: pd.DataFrame, y_test: pd.Series
    ) -> dict[str, float]:
        # Precision, recall, F1 and accuracy depend on the threshold; ROC AUC does not.
        y_proba = pipeline.predict_proba(X_test)[:, 1]
        y_pred = (y_proba >= self._evaluation_threshold).astype(int)

        return {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, y_proba)),
        }
