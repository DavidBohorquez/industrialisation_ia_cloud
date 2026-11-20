from typing import Literal, get_args

TARGET_COLUMN = "express_eligible"

# Canonical vocabulary (ADR-0011): the only category values the core, the model and the API know.
# Each data source maps its own values into these in an adapter under infrastructure/; it can
# rename a value, never invent detail its source does not have.
Weather = Literal["normal", "pluie", "neige", "orage", "vent"]  # vent: strong wind, no storm
DeliveryZone = Literal["centre", "banlieue", "rurale"]
CustomerType = Literal["particulier", "professionnel"]  # individual (B2C) or business (B2B)

NUMERIC_FEATURES = [
    "hour",
    "day_of_week",
    "weekend",
    "distance_km",
    "order_value_eur",
    "weight_kg",
    "stock_available",
    "preparation_time_min",
    "carrier_capacity",
]

CATEGORICAL_FEATURES = [
    "weather",
    "delivery_zone",
    "customer_type",
]

# Allowed values per categorical column, read from the Literals above (one source of truth).
CATEGORY_VALUES: dict[str, tuple[str, ...]] = {
    "weather": get_args(Weather),
    "delivery_zone": get_args(DeliveryZone),
    "customer_type": get_args(CustomerType),
}

# Les identifiants et les dates brutes ne sont pas utilisés par le modèle.
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
