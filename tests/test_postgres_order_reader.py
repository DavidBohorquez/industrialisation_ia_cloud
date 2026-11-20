import logging
from datetime import date

import psycopg
import pytest
from psycopg import sql

from livraison_express.abstractions.order_repository import OrderReader, OrderWriter
from livraison_express.infrastructure.postgres.postgres_order_reader import (
    PostgresOrderReader,
    connect_read_only,
)
from tests.erp_support import ORDER, canonical_to_erp_row

ERP_ROW = canonical_to_erp_row(ORDER)


def erp_row(order_id: str, **changes) -> dict:
    return {**ERP_ROW, "order_id": order_id, **changes}


# ---------- no database needed ----------


def test_reader_has_no_way_to_write():
    reader = PostgresOrderReader("postgresql://nobody@127.0.0.1:1/none")

    assert isinstance(reader, OrderReader)
    assert not isinstance(reader, OrderWriter)
    assert not hasattr(reader, "save")


def test_reader_connects_on_first_read_not_when_built():
    # Built at startup by the factory: the server is contacted by the first read only.
    reader = PostgresOrderReader("postgresql://nobody@127.0.0.1:1/none")

    with pytest.raises(psycopg.OperationalError):
        reader.count()


# ---------- against a PostgreSQL server ----------


@pytest.mark.postgres
@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO {table} (order_id, hour, day_of_week, distance_km, order_value_eur, "
        "weight_kg, stock_available, carrier_capacity, weather, delivery_zone, customer_type) "
        "VALUES ('X', 1, 1, 1, 1, 1, 1, 1, 'clear', 'centre', 'individual')",
        "UPDATE {table} SET express_eligible = 1",
        "DELETE FROM {table}",
        "CREATE TABLE {schema}.orders_copy (id INTEGER)",
    ],
)
def test_reader_connection_rejects_writes(erp_table, statement):
    # The test DSN is a superuser: only the connection's READ ONLY setting stops the write.
    erp_table.insert([ERP_ROW])
    query = sql.SQL(statement).format(
        table=erp_table.identifier, schema=sql.Identifier(erp_table.schema)
    )

    with connect_read_only(erp_table.dsn) as connection:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            connection.execute(query)

    assert erp_table.reader().get_all() == [ORDER]


@pytest.mark.postgres
def test_erp_gaps_are_translated(erp_table):
    erp_table.insert(
        [
            # Before 2015: no weekend column; before 2017: no preparation time.
            erp_row("ERP-1", order_date=date(2014, 3, 9), day_of_week=6, weekend=None,
                    preparation_time_min=None),
            # Outcome not known yet.
            erp_row("ERP-2", express_eligible=None),
        ]
    )
    reader = erp_table.reader()

    old = reader.get("ERP-1")
    assert (old["weekend"], old["preparation_time_min"]) == (1, None)
    assert old["order_date"] == date(2014, 3, 9)
    assert [o["order_id"] for o in reader.get_training_data()] == ["ERP-1"]
    assert reader.get("ERP-2")["express_eligible"] is None


@pytest.mark.postgres
def test_rows_that_cannot_be_translated_are_skipped_and_logged(erp_table, caplog):
    erp_table.insert(
        [
            erp_row("ERP-1"),
            erp_row("ERP-2", weather="hail"),
            erp_row("ERP-3", customer_type="vip", express_eligible=None),
            erp_row("ERP-4", weather="hail"),
        ]
    )
    reader = erp_table.reader()

    with caplog.at_level(logging.WARNING):
        orders = reader.get_all()

    assert [o["order_id"] for o in orders] == ["ERP-1"]
    # One warning: each distinct problem (field, value) with its count and order ids.
    [warning] = caplog.records
    assert "Skipped 3 of 4 ERP orders" in warning.getMessage()
    assert "unknown weather 'hail'" in warning.getMessage()
    assert "2 order(s), e.g. ERP-2, ERP-4" in warning.getMessage()
    assert "unknown customer_type 'vip'" in warning.getMessage()
    # Still counted: count() - len(get_all()) shows what was skipped.
    assert reader.count() == 4
    assert reader.get("ERP-2") is None
    assert [o["order_id"] for o in reader.get_training_data()] == ["ERP-1"]
