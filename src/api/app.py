import logging
import uuid
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from src.abstractions.explanation_generator import ExplanationGenerator
from src.api.schemas import (
    BatchRequest,
    BatchResponse,
    ErrorResponse,
    Explanation,
    HealthResponse,
    ModelInfoResponse,
    OrderRequest,
    PredictionResponse,
)
from src.core.domain import Prediction
from src.core.predictor import EligibilityPredictor

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
        response_model=HealthResponse,
        responses={503: {"model": HealthResponse, "description": "No model is loaded."}},
        tags=["monitoring"],
    )
    def health(response: Response) -> HealthResponse:
        if predictor is None:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return HealthResponse(status="unavailable", model_version=None)
        return HealthResponse(status="ok", model_version=predictor.model.version)

    @app.get("/v1/model", response_model=ModelInfoResponse, responses=UNAVAILABLE, tags=["model"])
    def model_info() -> ModelInfoResponse:
        current = require_predictor()
        return ModelInfoResponse(
            version=current.model.version,
            trained_at=current.model.trained_at,
            decision_threshold=current.threshold,
            features=current.model.features,
            metrics=current.model.metrics,
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
