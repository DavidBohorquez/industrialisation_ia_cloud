from datetime import date

import pytest

from livraison_express.infrastructure.postgres.erp_order_mapper import erp_row_to_order

# A row as the ERP stores it (its vocabulary, capacity in slots out of 50).
ERP_ROW = {
    "order_id": "ERP-00000042",
    "order_date": date(2026, 11, 20),
    "hour": 14,
    "day_of_week": 4,
    "weekend": 0,
    "distance_km": 12.5,
    "order_value_eur": 99.9,
    "weight_kg": 3.2,
    "stock_available": 1,
    "preparation_time_min": 20.5,
    "carrier_capacity": 40.0,
    "weather": "rain",
    "delivery_zone": "suburb",
    "customer_type": "business",
    "express_eligible": 1,
}


def row(**changes) -> dict:
    return {**ERP_ROW, **changes}


def test_complete_row_becomes_a_canonical_order():
    assert erp_row_to_order(ERP_ROW) == {
        "order_id": "ERP-00000042",
        "order_date": date(2026, 11, 20),
        "hour": 14,
        "day_of_week": 4,
        "weekend": 0,
        "distance_km": 12.5,
        "order_value_eur": 99.9,
        "weight_kg": 3.2,
        "stock_available": 1,
        "preparation_time_min": 20.5,
        "carrier_capacity": 0.8,
        "weather": "pluie",
        "delivery_zone": "banlieue",
        "customer_type": "professionnel",
        "express_eligible": 1,
    }


@pytest.mark.parametrize(
    ("erp", "canonical"),
    [("clear", "normal"), ("rain", "pluie"), ("snow", "neige"), ("wind", "vent")],
)
def test_weather(erp, canonical):
    assert erp_row_to_order(row(weather=erp))["weather"] == canonical


@pytest.mark.parametrize(
    ("erp", "canonical"),
    [("centre", "centre"), ("suburb", "banlieue"), ("rural", "rurale")],
)
def test_delivery_zone(erp, canonical):
    assert erp_row_to_order(row(delivery_zone=erp))["delivery_zone"] == canonical


@pytest.mark.parametrize(
    ("erp", "canonical"),
    [("individual", "particulier"), ("business", "professionnel")],
)
def test_customer_type(erp, canonical):
    assert erp_row_to_order(row(customer_type=erp))["customer_type"] == canonical


@pytest.mark.parametrize(
    ("slots", "share"),
    [(0, 0.0), (5, 0.1), (25, 0.5), (42.5, 0.85), (50, 1.0)],
)
def test_carrier_capacity_is_the_free_share_of_50_slots(slots, share):
    assert erp_row_to_order(row(carrier_capacity=slots))["carrier_capacity"] == pytest.approx(share)


def test_capacity_above_50_is_not_hidden():
    # Range checks belong to data quality (clean_orders_data drops it), not to the translation.
    assert erp_row_to_order(row(carrier_capacity=60))["carrier_capacity"] == pytest.approx(1.2)


@pytest.mark.parametrize(
    ("day_of_week", "weekend"),
    [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 1), (6, 1)],
)
def test_missing_weekend_is_derived_from_the_day(day_of_week, weekend):
    order = erp_row_to_order(row(day_of_week=day_of_week, weekend=None))

    assert order["weekend"] == weekend


def test_known_weekend_is_kept():
    assert erp_row_to_order(row(day_of_week=6, weekend=1))["weekend"] == 1


def test_missing_preparation_time_stays_missing():
    # Data quality decides what to do with it; inventing a value here would hide the gap.
    assert erp_row_to_order(row(preparation_time_min=None))["preparation_time_min"] is None


@pytest.mark.parametrize("label", [0, 1, None])
def test_label_is_kept_or_none_while_unknown(label):
    assert erp_row_to_order(row(express_eligible=label))["express_eligible"] == label


def test_order_date_stays_a_date():
    assert erp_row_to_order(ERP_ROW)["order_date"] == date(2026, 11, 20)


def test_numbers_have_the_model_types():
    order = erp_row_to_order(row(hour=14, distance_km=12, stock_available=1))

    assert type(order["hour"]) is int
    assert type(order["distance_km"]) is float
    assert type(order["stock_available"]) is int


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("weather", "hail"),
        ("weather", "Rain"),  # no guessing: case matters
        ("delivery_zone", "downtown"),
        ("customer_type", "vip"),
        ("express_eligible", 2),
    ],
)
def test_unknown_value_is_rejected(column, value):
    with pytest.raises(ValueError, match=f"unknown {column} {value!r}"):
        erp_row_to_order(row(**{column: value}))


@pytest.mark.parametrize("column", ["order_id", "hour", "distance_km", "carrier_capacity"])
def test_null_in_a_required_column_is_rejected(column):
    with pytest.raises(ValueError, match=f"{column} is NULL"):
        erp_row_to_order(row(**{column: None}))


def test_the_row_is_not_modified():
    erp_row = row(weekend=None)

    erp_row_to_order(erp_row)

    assert erp_row == row(weekend=None)
