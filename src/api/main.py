import logging

from fastapi import FastAPI

from src.api.app import create_app
from src.config import load_settings
from src.factory import build_explanation_generator, build_predictor

logger = logging.getLogger(__name__)


def build_app() -> FastAPI:
    settings = load_settings()

    try:
        predictor = build_predictor(settings)
    except FileNotFoundError as error:
        logger.warning("Starting without a model, predictions will return 503: %s", error)
        predictor = None

    return create_app(predictor, build_explanation_generator())


app = build_app()
