from typing import assert_never

from livraison_express.abstractions.experiment_tracker import ExperimentTracker
from livraison_express.abstractions.explanation_generator import ExplanationGenerator
from livraison_express.abstractions.model_repository import ModelRepository
from livraison_express.abstractions.order_repository import OrderReader
from livraison_express.config import Settings
from livraison_express.core.explanation import TemplateExplanationGenerator
from livraison_express.core.learning.ml_predict import MLPredict
from livraison_express.core.learning.ml_trainer import MLTrainer
from livraison_express.infrastructure.dev.file_model_repository import FileModelRepository
from livraison_express.infrastructure.dev.in_memory_order_repository import (
    InMemoryOrderRepository,
)
from livraison_express.infrastructure.dev.order_generator import generate_orders


def build_order_reader(settings: Settings) -> OrderReader:
    """Where jobs read orders from, chosen by ORDER_SOURCE (ADR-0013)."""
    match settings.order_source:
        case "memory":
            return InMemoryOrderRepository(generate_orders(random_state=settings.random_state))
        case "postgres":
            # Imported here: only jobs that read the ERP need psycopg, the API never imports it.
            from livraison_express.infrastructure.postgres.postgres_order_reader import (
                PostgresOrderReader,
            )

            # Settings guarantee the DSN is set when the source is postgres.
            return PostgresOrderReader(settings.postgres_dsn.get_secret_value())
        case _:
            assert_never(settings.order_source)


def build_model_repository(settings: Settings) -> ModelRepository:
    return FileModelRepository(settings.artifacts_dir)


def build_predictor(settings: Settings) -> MLPredict:
    model = build_model_repository(settings).load(settings.model_version)
    return MLPredict(model, threshold=settings.decision_threshold)


def build_trainer(settings: Settings) -> MLTrainer:
    return MLTrainer(
        random_state=settings.random_state,
        evaluation_threshold=settings.decision_threshold,
    )


def build_explanation_generator() -> ExplanationGenerator:
    return TemplateExplanationGenerator()


def build_experiment_tracker(settings: Settings) -> ExperimentTracker:
    # Imported here: MLflow takes ~2 s to import and only training needs it, not the API.
    from livraison_express.infrastructure.mlflow_tracking import MlflowExperimentTracker

    return MlflowExperimentTracker(
        tracking_uri=settings.mlflow_tracking_uri,
        artifact_location=settings.mlflow_artifact_location,
    )
