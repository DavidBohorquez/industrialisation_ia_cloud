from src.abstractions.explanation_generator import ExplanationGenerator
from src.abstractions.model_repository import ModelRepository
from src.abstractions.order_data_source import OrderDataSource
from src.config import Settings
from src.core.explanation import TemplateExplanationGenerator
from src.core.predictor import EligibilityPredictor
from src.infrastructure.dev.file_model_repository import FileModelRepository
from src.infrastructure.dev.synthetic_orders import SyntheticOrderSource


def build_order_source(settings: Settings) -> OrderDataSource:
    if settings.environment == "dev":
        return SyntheticOrderSource(random_state=settings.random_state)

    raise ValueError(
        f"Aucune source de commandes pour l'environnement '{settings.environment}'."
    )


def build_model_repository(settings: Settings) -> ModelRepository:
    if settings.environment == "dev":
        return FileModelRepository(settings.artifacts_dir)

    raise ValueError(
        f"Aucun stockage de modèle pour l'environnement '{settings.environment}'."
    )


def build_predictor(settings: Settings) -> EligibilityPredictor:
    model = build_model_repository(settings).load(settings.model_version)
    return EligibilityPredictor(model, threshold=settings.decision_threshold)


def build_explanation_generator() -> ExplanationGenerator:
    return TemplateExplanationGenerator()
