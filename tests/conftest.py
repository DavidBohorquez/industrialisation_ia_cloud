import pandas as pd
import pytest

from livraison_express.core.learning.ml_trainer import MLTrainer
from livraison_express.infrastructure.dev.order_generator import generate_orders


@pytest.fixture(scope="session")
def orders():
    return pd.DataFrame(generate_orders(n_rows=1000, random_state=0))


@pytest.fixture(scope="session")
def trained_model(orders):
    return MLTrainer(random_state=0, evaluation_threshold=0.5).train(orders, version="test")


@pytest.fixture
def valid_order():
    return {
        "hour": 10,
        "day_of_week": 1,
        "weekend": 0,
        "distance_km": 2,
        "order_value_eur": 50,
        "weight_kg": 1,
        "stock_available": 1,
        "preparation_time_min": 10,
        "carrier_capacity": 0.9,
        "weather": "normal",
        "delivery_zone": "centre",
        "customer_type": "premium",
    }
