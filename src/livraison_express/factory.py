from livraison_express.abstractions.explanation_generator import ExplanationGenerator
from livraison_express.abstractions.model_repository import ModelRepository
from livraison_express.abstractions.order_data_source import OrderDataSource
from livraison_express.config import Settings
from livraison_express.core.explanation import TemplateExplanationGenerator
from livraison_express.core.predictor import EligibilityPredictor
from livraison_express.infrastructure.dev.file_model_repository import FileModelRepository
from livraison_express.infrastructure.dev.synthetic_orders import SyntheticOrderSource


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
