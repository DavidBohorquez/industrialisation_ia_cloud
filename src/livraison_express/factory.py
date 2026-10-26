from livraison_express.abstractions.experiment_tracker import ExperimentTracker
from livraison_express.abstractions.explanation_generator import ExplanationGenerator
from livraison_express.abstractions.model_repository import ModelRepository
from livraison_express.abstractions.order_repository import OrderRepository
from livraison_express.config import Settings
from livraison_express.core.explanation import TemplateExplanationGenerator
from livraison_express.core.learning.ml_predict import MLPredict
from livraison_express.core.learning.ml_trainer import MLTrainer
from livraison_express.infrastructure.dev.file_model_repository import FileModelRepository
from livraison_express.infrastructure.dev.in_memory_order_repository import (
    InMemoryOrderRepository,
)
from livraison_express.infrastructure.dev.order_generator import generate_orders


def build_order_repository(settings: Settings) -> OrderRepository:
    if settings.environment == "dev":
        return InMemoryOrderRepository(generate_orders(random_state=settings.random_state))

    raise ValueError(
        f"Aucun stockage de commandes pour l'environnement '{settings.environment}'."
    )


def build_model_repository(settings: Settings) -> ModelRepository:
    if settings.environment == "dev":
        return FileModelRepository(settings.artifacts_dir)

    raise ValueError(
        f"Aucun stockage de modèle pour l'environnement '{settings.environment}'."
    )


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
