"""Test helpers: an ERP `orders` table in PostgreSQL, filled with rows in the ERP's own format.

Tests write through an admin connection (TEST_POSTGRES_DSN); the code under test only reads.
Each test gets its own schema, dropped afterwards: the tests never touch `public.orders`.
"""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg
from psycopg import sql

from livraison_express.infrastructure.postgres.erp_order_mapper import (
    CARRIER_MAX_CAPACITY,
    CUSTOMER_TYPE,
    DELIVERY_ZONE,
    ERP_COLUMNS,
    WEATHER,
)
from livraison_express.infrastructure.postgres.postgres_order_reader import PostgresOrderReader

# A canonical order (the application's vocabulary). Its values survive the trip through the
# ERP format exactly (45 / 50 == 0.9), so the reader must give back this very dict.
ORDER = {
    "order_id": "CMD-000001",
    "order_date": date(2026, 11, 20),
    "hour": 10,
    "day_of_week": 4,
    "weekend": 0,
    "distance_km": 2.5,
    "order_value_eur": 50.0,
    "weight_kg": 1.25,
    "stock_available": 1,
    "preparation_time_min": 10.0,
    "carrier_capacity": 0.9,
    "weather": "pluie",
    "delivery_zone": "banlieue",
    "customer_type": "professionnel",
    "express_eligible": 1,
}

# The ERP table contract (column names, types, NULL allowed or not).
ERP_ORDERS_DDL = """
CREATE TABLE {table} (
    order_id TEXT PRIMARY KEY,
    order_date DATE,
    hour INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    weekend INTEGER,
    distance_km DOUBLE PRECISION NOT NULL,
    order_value_eur DOUBLE PRECISION NOT NULL,
    weight_kg DOUBLE PRECISION NOT NULL,
    stock_available INTEGER NOT NULL,
    preparation_time_min DOUBLE PRECISION,
    carrier_capacity DOUBLE PRECISION NOT NULL,
    weather TEXT NOT NULL,
    delivery_zone TEXT NOT NULL,
    customer_type TEXT NOT NULL,
    express_eligible SMALLINT
)
"""


def _reverse(vocabulary: Mapping[str, str]) -> dict[str, str]:
    return {canonical: erp for erp, canonical in vocabulary.items()}


def canonical_to_erp_row(order: Mapping[str, Any]) -> dict[str, Any]:
    """Test only: the reverse of erp_order_mapper, to store canonical orders the ERP's way."""
    return {
        **{column: order[column] for column in ERP_COLUMNS},
        "carrier_capacity": order["carrier_capacity"] * CARRIER_MAX_CAPACITY,
        "weather": _reverse(WEATHER)[order["weather"]],
        "delivery_zone": _reverse(DELIVERY_ZONE)[order["delivery_zone"]],
        "customer_type": _reverse(CUSTOMER_TYPE)[order["customer_type"]],
    }


@dataclass(frozen=True)
class ErpTestTable:
    dsn: str
    schema: str

    @classmethod
    def create(cls, dsn: str) -> "ErpTestTable":
        table = cls(dsn, f"test_{uuid.uuid4().hex[:12]}")
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(table.schema)))
            admin.execute(sql.SQL(ERP_ORDERS_DDL).format(table=table.identifier))
        return table

    @property
    def identifier(self) -> sql.Identifier:
        return sql.Identifier(self.schema, "orders")

    def insert(self, rows: Iterable[Mapping[str, Any]]) -> None:
        query = sql.SQL("INSERT INTO {table} ({columns}) VALUES ({values})").format(
            table=self.identifier,
            columns=sql.SQL(", ").join(map(sql.Identifier, ERP_COLUMNS)),
            values=sql.SQL(", ").join(sql.Placeholder(column) for column in ERP_COLUMNS),
        )
        with psycopg.connect(self.dsn) as admin:
            admin.cursor().executemany(query, list(rows))

    def reader(self) -> PostgresOrderReader:
        return PostgresOrderReader(self.dsn, schema=self.schema)

    def drop(self) -> None:
        with psycopg.connect(self.dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))
