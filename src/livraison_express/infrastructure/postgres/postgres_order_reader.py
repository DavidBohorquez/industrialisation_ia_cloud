"""Reads orders from the ERP's PostgreSQL database (a read replica, ADR-0009). Never writes.

PostgresOrderReader implements OrderReader only, not OrderWriter: it has no `save` method, so
the application cannot write into the company's database by construction (ADR-0012).
"""

import logging
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from livraison_express.abstractions.order_repository import OrderReader
from livraison_express.infrastructure.postgres.erp_order_mapper import (
    ERP_COLUMNS,
    erp_row_to_order,
)

logger = logging.getLogger(__name__)

TABLE = "orders"
CONNECT_TIMEOUT_SECONDS = 10

# COLLATE "C": byte order, the same as Python's sorted() and the same on every server,
# whatever its locale (the contract sorts by order_id).
ORDER_BY_ID = sql.SQL(' ORDER BY order_id COLLATE "C"')


def connect_read_only(dsn: str) -> psycopg.Connection:
    """Open a connection whose transactions are all READ ONLY: PostgreSQL rejects any write.

    Defense in depth: the database role is read-only too (ADR-0009, ADR-0012).
    """
    connection = psycopg.connect(
        dsn, row_factory=dict_row, connect_timeout=CONNECT_TIMEOUT_SECONDS
    )
    # Each transaction now starts with BEGIN READ ONLY.
    connection.read_only = True
    return connection


class PostgresOrderReader(OrderReader):
    """One short connection per call: nothing is held open between the steps of a job."""

    def __init__(self, dsn: str, schema: str = "public"):
        # The DSN holds a password: kept private, never logged, not part of repr().
        self._dsn = dsn
        table = sql.Identifier(schema, TABLE)
        columns = sql.SQL(", ").join(sql.Identifier(column) for column in ERP_COLUMNS)
        # Explicit columns: a column the ERP adds later does not change what is read.
        self._select = sql.SQL("SELECT {columns} FROM {table}").format(
            columns=columns, table=table
        )
        self._count = sql.SQL("SELECT count(*) AS orders FROM {table}").format(table=table)

    def get(self, order_id: str) -> dict[str, Any] | None:
        rows = self._fetch(self._select + sql.SQL(" WHERE order_id = %s"), (order_id,))
        # An order that cannot be translated is not returned, as in get_all().
        orders = self._translate(rows)
        return orders[0] if orders else None

    def get_all(self) -> list[dict[str, Any]]:
        return self._translate(self._fetch(self._select + ORDER_BY_ID))

    def count(self) -> int:
        return self._fetch(self._count)[0]["orders"]

    def get_training_data(self) -> list[dict[str, Any]]:
        labelled = sql.SQL(" WHERE express_eligible IS NOT NULL")
        return self._translate(self._fetch(self._select + labelled + ORDER_BY_ID))

    def _fetch(self, query: sql.Composable, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        # The context manager ends the transaction and closes the connection.
        with connect_read_only(self._dsn) as connection:
            return connection.execute(query, params).fetchall()

    @staticmethod
    def _translate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        orders: list[dict[str, Any]] = []
        errors: list[str] = []
        for row in rows:
            try:
                orders.append(erp_row_to_order(row))
            except ValueError as error:
                errors.append(f"{row['order_id']}: {error}")

        if errors:
            logger.warning(
                "Skipped %d of %d ERP orders that cannot be translated, first: %s",
                len(errors),
                len(rows),
                errors[0],
            )
        return orders
