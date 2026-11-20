import logging
from datetime import date, timedelta

import pytest
from config import SimulationConfig
from generator import OrderGenerator
from outcome import express_eligible
from simulator import ErpSimulator

TODAY = date(2026, 11, 20)
OLD, RECENT = 60, 40  # history sizes: the 60 old orders all date from 2015 (no preparation time)


class FakeStore:
    """What both writers offer: insert-if-absent, outcomes that never change once set."""

    def __init__(self):
        self.rows = {}

    def write(self, orders):
        new = [order for order in orders if order["order_id"] not in self.rows]
        for order in new:
            self.rows[order["order_id"]] = {**order, "express_eligible": None}
        return len(new)

    def close(self):
        pass

    def set_outcomes(self, outcomes):
        updated = 0
        for order_id, outcome in outcomes.items():
            row = self.rows.get(order_id)
            if row is not None and row["express_eligible"] is None:
                row["express_eligible"] = outcome
                updated += 1
        return updated


class FakeMongo(FakeStore):
    """Like MongoWriter: no counting, no clock."""


class FakePostgres(FakeStore):
    """Like PostgresWriter: also counts orders and gives the simulated clock."""

    def count_from(self, start, end):
        return sum(start <= row["order_date"] < end for row in self.rows.values())

    def next_sequence(self):
        return max((int(order_id[4:]) for order_id in self.rows), default=0)

    def last_order_date(self):
        return max((row["order_date"] for row in self.rows.values()), default=None)

    def pending_outcomes(self, known_until):
        return [
            dict(row)
            for row in self.rows.values()
            if row["express_eligible"] is None
            and row["preparation_time_min"] is not None
            and row["order_date"] <= known_until
        ]


def run(postgres, mongo, live_orders, **settings):
    config = SimulationConfig(
        postgres_dsn="",
        mongo_uri="",
        batch_size=10,
        interval_seconds=0,
        postgres_old_history_orders=OLD,
        recent_history_orders=RECENT,
        live_order_limit=OLD + RECENT + live_orders,
        today=TODAY,
        **settings,
    )
    ErpSimulator(config, OrderGenerator(), postgres, mongo, logging.getLogger("test")).run()


def live_rows(store):
    return [row for row in store.rows.values() if row["order_date"] >= TODAY]


@pytest.fixture
def stores():
    postgres, mongo = FakePostgres(), FakeMongo()
    run(postgres, mongo, live_orders=50)  # 5 batches: 20 to 24 November
    return postgres, mongo


def test_each_batch_moves_the_simulated_clock_one_day(stores):
    postgres, _ = stores

    assert sorted({row["order_date"] for row in live_rows(postgres)}) == [
        TODAY + timedelta(days=n) for n in range(5)
    ]


def test_outcomes_are_revealed_after_the_label_delay(stores):
    postgres, _ = stores
    known_until = TODAY + timedelta(days=4 - 2)  # last simulated day minus LABEL_DELAY_DAYS

    for row in postgres.rows.values():
        if row["preparation_time_min"] is None or row["order_date"] > known_until:
            assert row["express_eligible"] is None, row["order_id"]
        else:
            assert row["express_eligible"] == express_eligible(row), row["order_id"]


def test_old_orders_without_preparation_time_never_get_an_outcome(stores):
    postgres, _ = stores
    old_rows = [row for row in postgres.rows.values() if row["order_date"] < date(2017, 7, 1)]

    assert len(old_rows) == OLD
    assert all(row["express_eligible"] is None for row in old_rows)


def test_mongo_receives_the_same_outcomes_for_the_orders_it_holds(stores):
    postgres, mongo = stores

    assert set(mongo.rows) < set(postgres.rows)  # no pre-2023 history in MongoDB
    assert any(row["express_eligible"] is not None for row in mongo.rows.values())
    for order_id, row in mongo.rows.items():
        assert row["express_eligible"] == postgres.rows[order_id]["express_eligible"]


def test_a_restart_resumes_the_clock_and_keeps_known_outcomes(stores):
    postgres, mongo = stores
    known_before = {
        order_id: row["express_eligible"]
        for order_id, row in postgres.rows.items()
        if row["express_eligible"] is not None
    }

    run(postgres, mongo, live_orders=80)  # restart: 3 more batches

    new_dates = sorted({row["order_date"] for row in live_rows(postgres)})
    assert new_dates[-3:] == [TODAY + timedelta(days=n) for n in (5, 6, 7)]  # not back to TODAY
    assert all(postgres.rows[order_id]["express_eligible"] == y for order_id, y in known_before.items())
    # The clock moved on, so the orders of 23 and 24 November now have their outcome.
    assert all(
        row["express_eligible"] is not None
        for row in live_rows(postgres)
        if row["order_date"] <= TODAY + timedelta(days=5)
    )


def test_the_label_delay_is_configurable():
    postgres, mongo = FakePostgres(), FakeMongo()

    run(postgres, mongo, live_orders=30, label_delay_days=0)

    assert all(row["express_eligible"] is not None for row in live_rows(postgres))
