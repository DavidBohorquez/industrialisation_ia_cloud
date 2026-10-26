from datetime import datetime, timezone

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from livraison_express.abstractions.model_repository import ModelRepository
from livraison_express.abstractions.order_data_source import OrderDataSource
from livraison_express.core.data_quality import clean_orders_data, validate_dataset
from livraison_express.core.domain import TrainedModel
from livraison_express.core.features import FEATURE_COLUMNS, TARGET_COLUMN, build_preprocessor


def build_pipeline(random_state: int) -> Pipeline:
    classifier = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        random_state=random_state,
    )
    return Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            ("classifier", classifier),
        ]
    )


def evaluate(pipeline: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, float]:
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    return {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
    }


def train_model(
    orders: pd.DataFrame,
    version: str,
    random_state: int,
    test_size: float = 0.20,
) -> TrainedModel:
    X_train, X_test, y_train, y_test = train_test_split(
        orders[FEATURE_COLUMNS],
        orders[TARGET_COLUMN],
        test_size=test_size,
        random_state=random_state,
        stratify=orders[TARGET_COLUMN],
    )

    pipeline = build_pipeline(random_state)
    pipeline.fit(X_train, y_train)

    return TrainedModel(
        pipeline=pipeline,
        version=version,
        features=list(FEATURE_COLUMNS),
        metrics=evaluate(pipeline, X_test, y_test),
        trained_at=datetime.now(timezone.utc).isoformat(),
    )


def run_training(
    source: OrderDataSource,
    repository: ModelRepository,
    version: str,
    random_state: int,
) -> TrainedModel:
    orders = clean_orders_data(source.load_orders())
    validate_dataset(orders)

    model = train_model(orders, version, random_state)
    repository.save(model)

    return model
