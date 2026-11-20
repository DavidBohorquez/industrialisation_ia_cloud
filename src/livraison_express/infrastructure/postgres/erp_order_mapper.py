"""Translates a row of the ERP's `orders` table into a canonical order (anti-corruption layer).

The ERP has its own vocabulary (English categories, capacity in slots, columns added over the
years); the application keeps its own (ADR-0011). This module is the only place that knows both.
Pure functions, no database: tests/test_erp_order_mapper.py checks every rule without one.

A row that cannot be translated raises ValueError. The reader skips it and logs a warning:
an unknown value is never passed through to training.
"""

from collections.abc import Mapping
from typing import Any

# Columns read from the ERP table, in the order of its contract.
ERP_COLUMNS = (
    "order_id",
    "order_date",
    "hour",
    "day_of_week",
    "weekend",
    "distance_km",
    "order_value_eur",
    "weight_kg",
    "stock_available",
    "preparation_time_min",
    "carrier_capacity",
    "weather",
    "delivery_zone",
    "customer_type",
    "express_eligible",
)

# ERP value -> canonical value. Written out here rather than derived from core/features.py:
# this is the contract with one source, and a value missing from it must fail loudly.
WEATHER = {"clear": "normal", "rain": "pluie", "snow": "neige", "wind": "vent"}
DELIVERY_ZONE = {"centre": "centre", "suburb": "banlieue", "rural": "rurale"}
CUSTOMER_TYPE = {"individual": "particulier", "business": "professionnel"}
LABELS = (0, 1)

# Assumption: the ERP stores the carrier's free capacity as a number of slots out of 50.
# The model expects the free share, between 0 and 1.
CARRIER_MAX_CAPACITY = 50

# day_of_week: Monday = 0 ... Saturday = 5, Sunday = 6.
FIRST_WEEKEND_DAY = 5


def erp_row_to_order(row: Mapping[str, Any]) -> dict[str, Any]:
    """One ERP row (column name -> value) -> one canonical order. ValueError if impossible."""
    day_of_week = int(_required(row, "day_of_week"))

    return {
        "order_id": str(_required(row, "order_id")),
        "order_date": row["order_date"],
        "hour": int(_required(row, "hour")),
        "day_of_week": day_of_week,
        "weekend": _weekend(row["weekend"], day_of_week),
        "distance_km": float(_required(row, "distance_km")),
        "order_value_eur": float(_required(row, "order_value_eur")),
        "weight_kg": float(_required(row, "weight_kg")),
        "stock_available": int(_required(row, "stock_available")),
        # NULL before the ERP added the column (2017): left missing, never invented. What to do
        # with such orders is decided by data quality (clean_orders_data), not by the adapter.
        "preparation_time_min": _optional_float(row["preparation_time_min"]),
        "carrier_capacity": float(_required(row, "carrier_capacity")) / CARRIER_MAX_CAPACITY,
        "weather": _translate(row, "weather", WEATHER),
        "delivery_zone": _translate(row, "delivery_zone", DELIVERY_ZONE),
        "customer_type": _translate(row, "customer_type", CUSTOMER_TYPE),
        "express_eligible": _label(row["express_eligible"]),
    }


def _required(row: Mapping[str, Any], column: str) -> Any:
    value = row[column]
    if value is None:
        raise ValueError(f"{column} is NULL")
    return value


def _weekend(value: Any, day_of_week: int) -> int:
    # NULL before the ERP added the column (2015): it is fully determined by the day.
    if value is None:
        return int(day_of_week >= FIRST_WEEKEND_DAY)
    return int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _translate(row: Mapping[str, Any], column: str, vocabulary: Mapping[str, str]) -> str:
    value = row[column]
    if value not in vocabulary:
        raise ValueError(
            f"unknown {column} {value!r} (expected one of {', '.join(sorted(vocabulary))})"
        )
    return vocabulary[value]


def _label(value: Any) -> int | None:
    # NULL while the outcome is not known yet: such an order is not used for training.
    if value is None:
        return None
    if value not in LABELS:
        raise ValueError(f"unknown express_eligible {value!r} (expected 0, 1 or NULL)")
    return int(value)
