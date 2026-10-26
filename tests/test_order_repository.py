import pytest

from livraison_express.abstractions.order_repository import OrderRepository
from livraison_express.infrastructure.dev.in_memory_order_repository import (
    InMemoryOrderRepository,
)
from livraison_express.infrastructure.dev.order_generator import generate_orders

# Contract tests: a future PostgreSQL implementation is added to this list and must pass them all.
IMPLEMENTATIONS = [InMemoryOrderRepository]


@pytest.fixture(params=IMPLEMENTATIONS)
def repository(request) -> OrderRepository:
    return request.param()


@pytest.fixture
def order(valid_order):
    return {**valid_order, "order_id": "CMD-000001", "express_eligible": 1}


def test_saved_order_can_be_read_back(repository, order):
    repository.save(order)

    assert repository.get("CMD-000001") == order
    assert repository.get_all() == [order]
    assert repository.count() == 1


def test_same_order_id_replaces_instead_of_duplicating(repository, order):
    repository.save(order)
    repository.save({**order, "distance_km": 9})

    assert repository.count() == 1
    assert repository.get("CMD-000001")["distance_km"] == 9


def test_unknown_order_id_returns_none(repository):
    assert repository.get("CMD-UNKNOWN") is None


def test_order_without_id_is_rejected(repository, valid_order):
    with pytest.raises(ValueError, match="order_id"):
        repository.save(valid_order)


def test_returned_orders_are_copies(repository, order):
    repository.save(order)

    repository.get("CMD-000001")["distance_km"] = 999
    repository.get_all()[0]["distance_km"] = 999

    assert repository.get("CMD-000001")["distance_km"] == order["distance_km"]


def test_training_data_only_contains_orders_with_an_outcome(repository, order):
    repository.save(order)
    repository.save({**order, "order_id": "CMD-000002", "express_eligible": None})

    assert [o["order_id"] for o in repository.get_training_data()] == ["CMD-000001"]


def test_generated_orders_are_reproducible_and_labelled():
    first = generate_orders(n_rows=50, random_state=3)

    assert first == generate_orders(n_rows=50, random_state=3)
    assert len({o["order_id"] for o in first}) == 50
    assert all(o["express_eligible"] in (0, 1) for o in first)
