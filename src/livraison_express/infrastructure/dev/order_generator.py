from typing import Any, get_args

import numpy as np
import pandas as pd

from livraison_express.core.features import CustomerType, DeliveryZone, Weather

# Same penalties as the ERP simulator's labelling heuristic (ADR-0010), in canonical values.
# banlieue 0.175: one value now covers the notebook's proche_banlieue (0.10) and banlieue (0.25),
# as the ERP's "suburb" does; 0.175 is their mean.
ZONE_PENALTY = {
    "centre": 0,
    "banlieue": 0.175,
    "rurale": 0.45,
}

WEATHER_PENALTY = {
    "normal": 0,
    "pluie": 0.10,
    "neige": 0.25,
    "orage": 0.30,
    "vent": 0.20,
}

CUSTOMER_BONUS = {
    "particulier": 0,
    "professionnel": 0.15,
}


def generate_orders(n_rows: int = 6000, random_state: int = 42) -> list[dict[str, Any]]:
    """Synthetic labelled orders for dev and tests: there is no real data source in dev.

    Based on notebook cell 8: same seed handling, numeric distributions and latent-score formula.
    Only the categories differ (ADR-0011): they use the canonical vocabulary (vent added,
    proche_banlieue merged into banlieue, particulier/professionnel instead of standard/premium)
    and the penalties of the ERP simulator's labelling heuristic (ADR-0010), so that dev data
    follows the same rules as ERP data. The notebook keeps the original version (ADR-0002).
    """
    rng = np.random.default_rng(random_state)

    order_date = pd.date_range(start="2025-01-01", end="2025-12-31", periods=n_rows)

    hour = rng.integers(7, 23, size=n_rows)
    day_of_week = pd.Series(order_date).dt.day_of_week.to_numpy()
    weekend = (day_of_week >= 5).astype(int)

    data = pd.DataFrame({
        "order_id": [f"CMD-{i:06d}" for i in range(1, n_rows + 1)],
        "order_date": order_date,
        "hour": hour,
        "day_of_week": day_of_week,
        "weekend": weekend,
        "distance_km": np.round(rng.gamma(shape=2.0, scale=4.0, size=n_rows), 2),
        "order_value_eur": np.round(rng.uniform(10, 250, size=n_rows), 2),
        "weight_kg": np.round(rng.uniform(0.2, 25, size=n_rows), 2),
        "stock_available": rng.binomial(1, 0.85, size=n_rows),
        "preparation_time_min": np.round(
            rng.normal(loc=25, scale=10, size=n_rows).clip(5, 90), 1
        ),
        "carrier_capacity": np.round(rng.uniform(0.2, 1.0, size=n_rows), 2),
        "weather": rng.choice(
            list(get_args(Weather)),
            size=n_rows,
            p=[0.60, 0.20, 0.08, 0.04, 0.08],
        ),
        "delivery_zone": rng.choice(
            list(get_args(DeliveryZone)),
            size=n_rows,
            p=[0.30, 0.55, 0.15],
        ),
        "customer_type": rng.choice(
            list(get_args(CustomerType)),
            size=n_rows,
            p=[0.80, 0.20],
        ),
    })

    zone_penalty = data["delivery_zone"].map(ZONE_PENALTY)
    weather_penalty = data["weather"].map(WEATHER_PENALTY)
    customer_bonus = data["customer_type"].map(CUSTOMER_BONUS)

    # Score latent simulant une décision métier
    score = (
        2.5
        - 0.18 * data["distance_km"]
        - 0.035 * data["preparation_time_min"]
        - 0.035 * data["weight_kg"]
        - zone_penalty
        - weather_penalty
        + 1.8 * data["stock_available"]
        + 1.3 * data["carrier_capacity"]
        + customer_bonus
        - 0.40 * data["weekend"]
        - 0.08 * np.maximum(data["hour"] - 18, 0)
    )

    probability = 1 / (1 + np.exp(-score))
    data["express_eligible"] = rng.binomial(1, probability)

    # The DataFrame is a detail of the generation: orders leave this module as dicts.
    return data.to_dict(orient="records")
