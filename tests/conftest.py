import pytest

from livraison_express.core.training import train_model
from livraison_express.infrastructure.dev.synthetic_orders import SyntheticOrderSource


@pytest.fixture(scope="session")
def orders():
    return SyntheticOrderSource(n_rows=1000, random_state=0).load_orders()


@pytest.fixture(scope="session")
def trained_model(orders):
    return train_model(orders, version="test", random_state=0, evaluation_threshold=0.5)


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
