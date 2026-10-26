from typing import Literal

TARGET_COLUMN = "express_eligible"

Weather = Literal["normal", "pluie", "neige", "orage"]
DeliveryZone = Literal["centre", "proche_banlieue", "banlieue", "rurale"]
CustomerType = Literal["standard", "premium"]

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

# Les identifiants et les dates brutes ne sont pas utilisés par le modèle.
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
