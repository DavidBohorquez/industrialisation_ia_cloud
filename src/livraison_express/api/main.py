import logging

from fastapi import FastAPI

from livraison_express.api.app import create_app
from livraison_express.config import load_settings
from livraison_express.factory import build_explanation_generator, build_predictor
from livraison_express.logging_config import configure_logging

logger = logging.getLogger(__name__)


def build_app() -> FastAPI:
    settings = load_settings()
    configure_logging(settings.log_level)

    try:
        predictor = build_predictor(settings)
        logger.info("Model %s loaded from %s", settings.model_version, settings.artifacts_dir)
    except FileNotFoundError as error:
        logger.warning("Starting without a model, predictions will return 503: %s", error)
        predictor = None

    return create_app(predictor, build_explanation_generator())


app = build_app()
