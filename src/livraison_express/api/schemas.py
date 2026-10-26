from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from livraison_express.core.features import CustomerType, DeliveryZone, Weather

EXAMPLE_ORDER = {
    "hour": 14,
    "day_of_week": 2,
    "weekend": 0,
    "distance_km": 3.5,
    "order_value_eur": 89.9,
    "weight_kg": 2.4,
    "stock_available": 1,
    "preparation_time_min": 18,
    "carrier_capacity": 0.85,
    "weather": "normal",
    "delivery_zone": "centre",
    "customer_type": "premium",
}


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [EXAMPLE_ORDER]})

    hour: int = Field(ge=0, le=23, description="Hour the order was placed (0-23).")
    day_of_week: int = Field(ge=0, le=6, description="0 = Monday ... 6 = Sunday.")
    weekend: int = Field(ge=0, le=1, description="1 if day_of_week is 5 or 6, otherwise 0.")
    distance_km: float = Field(ge=0, description="Delivery distance in kilometres.")
    order_value_eur: float = Field(ge=0, description="Order amount in euros.")
    weight_kg: float = Field(ge=0, description="Parcel weight in kilograms.")
    stock_available: int = Field(ge=0, le=1, description="1 if every item is in stock.")
    preparation_time_min: float = Field(ge=0, description="Estimated preparation time in minutes.")
    carrier_capacity: float = Field(ge=0, le=1, description="Share of carrier capacity still free (0-1).")
    weather: Weather
    delivery_zone: DeliveryZone
    customer_type: CustomerType

    @model_validator(mode="after")
    def weekend_matches_day(self) -> "OrderRequest":
        if self.weekend != int(self.day_of_week >= 5):
            raise ValueError(
                "weekend must be 1 when day_of_week is 5 or 6 (Saturday, Sunday), otherwise 0"
            )
        return self


class Explanation(BaseModel):
    text: str
    source: str = Field(description='"template" today; "llm" once an LLM generator is plugged in.')
    top_factors: list[str] = Field(description="Features that weighed most on this decision.")


class PredictionResponse(BaseModel):
    express_eligible: bool
    decision: Literal["oui", "non"]
    probability: float = Field(ge=0, le=1)
    model_version: str
    prediction_timestamp: str
    explanation: Explanation | None = None


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    orders: list[OrderRequest] = Field(min_length=1)


class BatchResponse(BaseModel):
    predictions: list[PredictionResponse]


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    model_version: str | None


class ModelInfoResponse(BaseModel):
    version: str
    trained_at: str
    decision_threshold: float
    features: list[str]
    metrics: dict[str, float]


class ErrorResponse(BaseModel):
    detail: str
    reference: str | None = None
