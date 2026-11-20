import pytest

from livraison_express.core.features import CATEGORY_VALUES
from livraison_express.infrastructure.dev.order_generator import (
    CUSTOMER_BONUS,
    WEATHER_PENALTY,
    ZONE_PENALTY,
)


@pytest.mark.parametrize(
    ("column", "table"),
    [
        ("weather", WEATHER_PENALTY),
        ("delivery_zone", ZONE_PENALTY),
        ("customer_type", CUSTOMER_BONUS),
    ],
)
def test_every_canonical_value_has_a_penalty(column, table):
    # A value without an entry would give a NaN score, so a NaN probability.
    assert set(table) == set(CATEGORY_VALUES[column])


def test_generated_orders_use_every_canonical_value_and_only_those(orders):
    for column, allowed in CATEGORY_VALUES.items():
        assert set(orders[column]) == set(allowed), column
