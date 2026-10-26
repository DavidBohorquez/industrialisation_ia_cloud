import logging
import uuid
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from livraison_express.abstractions.explanation_generator import ExplanationGenerator
from livraison_express.api.schemas import (
    BatchRequest,
    BatchResponse,
    ErrorResponse,
    Explanation,
    LivenessResponse,
    ModelInfoResponse,
    OrderRequest,
    PredictionResponse,
    ReadinessResponse,
)
from livraison_express.core.domain import Prediction
from livraison_express.core.predictor import EligibilityPredictor

API_VERSION = "1.0.0"
MAX_BATCH_SIZE = 1000

logger = logging.getLogger(__name__)

UNAVAILABLE = {503: {"model": ErrorResponse, "description": "No model is loaded."}}


def create_app(
    predictor: EligibilityPredictor | None,
    explainer: ExplanationGenerator,
) -> FastAPI:
    app = FastAPI(
        title="Express Delivery Eligibility API",
        version=API_VERSION,
        description="Predicts whether an order can be delivered express (same day). "
        "Decision aid only: it does not replace business rules.",
    )

    def require_predictor() -> EligibilityPredictor:
        if predictor is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Prediction service temporarily unavailable: no model is loaded.",
            )
        return predictor

    def to_response(
        current: EligibilityPredictor,
        prediction: Prediction,
        order: Mapping[str, Any],
        explain: bool,
    ) -> PredictionResponse:
        explanation = None
        if explain:
            factors = current.top_factors(order)
            explanation = Explanation(
                text=explainer.explain(prediction, factors, order),
                source=explainer.source,
                top_factors=[factor.feature for factor in factors],
            )
        return PredictionResponse(**prediction.to_dict(), explanation=explanation)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        reference = uuid.uuid4().hex[:8]
        logger.exception("Unexpected error, reference %s", reference)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal error. Contact support with this reference.",
                "reference": reference,
            },
        )

    @app.get(
        "/health",
        response_model=LivenessResponse,
        tags=["monitoring"],
        summary="Liveness: the process is running.",
    )
    def liveness() -> LivenessResponse:
        return LivenessResponse(status="alive")

    @app.get(
        "/health/ready",
        response_model=ReadinessResponse,
        responses={503: {"model": ReadinessResponse, "description": "No model is loaded."}},
        tags=["monitoring"],
        summary="Readiness: a model is loaded and predictions can be served.",
    )
    def readiness(response: Response) -> ReadinessResponse:
        if predictor is None:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return ReadinessResponse(status="not_ready", model_version=None)
        return ReadinessResponse(status="ready", model_version=predictor.model.card.model_version)

    @app.get("/v1/model", response_model=ModelInfoResponse, responses=UNAVAILABLE, tags=["model"])
    def model_info() -> ModelInfoResponse:
        current = require_predictor()
        card = current.model.card
        return ModelInfoResponse(
            project=card.project,
            version=card.model_version,
            model_type=card.model_type,
            task=card.task,
            target=card.target,
            trained_at=card.trained_at,
            decision_threshold=current.threshold,
            evaluation_threshold=card.evaluation_threshold,
            features=card.features,
            metrics=card.metrics,
            limitations=card.limitations,
        )

    @app.post(
        "/v1/predictions",
        response_model=PredictionResponse,
        responses=UNAVAILABLE,
        tags=["predictions"],
    )
    def predict(order: OrderRequest, explain: bool = True) -> PredictionResponse:
        current = require_predictor()
        data = order.model_dump()
        return to_response(current, current.predict_one(data), data, explain)

    @app.post(
        "/v1/predictions/batch",
        response_model=BatchResponse,
        responses={
            413: {"model": ErrorResponse, "description": f"More than {MAX_BATCH_SIZE} orders."},
            **UNAVAILABLE,
        },
        tags=["predictions"],
    )
    def predict_batch(request: BatchRequest, explain: bool = False) -> BatchResponse:
        current = require_predictor()

        if len(request.orders) > MAX_BATCH_SIZE:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"Batch limited to {MAX_BATCH_SIZE} orders (received {len(request.orders)}).",
            )

        orders = [order.model_dump() for order in request.orders]
        predictions = current.predict_many(orders)

        return BatchResponse(
            predictions=[
                to_response(current, prediction, order, explain)
                for prediction, order in zip(predictions, orders)
            ]
        )

    return app
