import pytest

from livraison_express.abstractions.order_repository import OrderReader, OrderRepository
from livraison_express.infrastructure.dev.in_memory_order_repository import (
    InMemoryOrderRepository,
)
from livraison_express.infrastructure.dev.order_generator import generate_orders
from tests.erp_support import ORDER, canonical_to_erp_row

# Contract tests (ADR-0005, ADR-0012). A new implementation is added to one list and must pass
# every test of it: READERS for any OrderReader, REPOSITORIES for read + write stores.
READERS = ["memory", pytest.param("postgres", marks=pytest.mark.postgres)]
REPOSITORIES = [InMemoryOrderRepository]


def order(order_id: str, **changes) -> dict:
    return {**ORDER, "order_id": order_id, **changes}


@pytest.fixture(params=READERS)
def make_reader(request):
    """A function: canonical orders -> a reader holding them, each store seeded in its own format."""
    if request.param == "memory":
        return InMemoryOrderRepository

    erp_table = request.getfixturevalue("erp_table")  # skipped without TEST_POSTGRES_DSN

    def make(orders: list[dict]) -> OrderReader:
        erp_table.insert(canonical_to_erp_row(o) for o in orders)
        return erp_table.reader()

    return make


# ---------- OrderReader contract ----------


def test_orders_are_read_back_unchanged(make_reader):
    reader = make_reader([ORDER])

    assert reader.get("CMD-000001") == ORDER
    assert reader.get_all() == [ORDER]
    assert reader.count() == 1


def test_unknown_order_id_returns_none(make_reader):
    assert make_reader([ORDER]).get("CMD-UNKNOWN") is None


def test_empty_store(make_reader):
    reader = make_reader([])

    assert reader.get_all() == []
    assert reader.get_training_data() == []
    assert reader.count() == 0


def test_orders_are_sorted_by_order_id(make_reader):
    # Python's order (code points): uppercase < "_" < lowercase, "-" < digits. A database
    # sorting with its locale's rules instead would give another order.
    ids = ["ERP-10", "erp-0", "ERP_3", "ERP-2", "ERP-1"]
    reader = make_reader([order(order_id) for order_id in ids])

    assert [o["order_id"] for o in reader.get_all()] == sorted(ids)
    assert [o["order_id"] for o in reader.get_training_data()] == sorted(ids)


def test_training_data_only_contains_orders_with_an_outcome(make_reader):
    reader = make_reader(
        [
            order("CMD-000003", express_eligible=0),
            order("CMD-000002", express_eligible=None),
            order("CMD-000001", express_eligible=1),
        ]
    )

    training = reader.get_training_data()

    assert [(o["order_id"], o["express_eligible"]) for o in training] == [
        ("CMD-000001", 1),
        ("CMD-000003", 0),
    ]
    assert reader.count() == 3


def test_returned_orders_are_copies(make_reader):
    reader = make_reader([ORDER])

    reader.get("CMD-000001")["distance_km"] = 999
    reader.get_all()[0]["distance_km"] = 999
    reader.get_training_data()[0]["distance_km"] = 999

    assert reader.get("CMD-000001")["distance_km"] == ORDER["distance_km"]


# ---------- OrderWriter contract (stores the application owns) ----------


@pytest.fixture(params=REPOSITORIES)
def repository(request) -> OrderRepository:
    return request.param()


def test_saved_order_can_be_read_back(repository):
    repository.save(ORDER)

    assert repository.get("CMD-000001") == ORDER
    assert repository.count() == 1


def test_same_order_id_replaces_instead_of_duplicating(repository):
    repository.save(ORDER)
    repository.save({**ORDER, "distance_km": 9})

    assert repository.count() == 1
    assert repository.get("CMD-000001")["distance_km"] == 9


def test_order_without_id_is_rejected(repository):
    without_id = {key: value for key, value in ORDER.items() if key != "order_id"}

    with pytest.raises(ValueError, match="order_id"):
        repository.save(without_id)


def test_saved_order_is_a_copy(repository):
    original = dict(ORDER)
    repository.save(original)

    original["distance_km"] = 999

    assert repository.get("CMD-000001")["distance_km"] == ORDER["distance_km"]


# ---------- dev data ----------


def test_generated_orders_are_reproducible_and_labelled():
    first = generate_orders(n_rows=50, random_state=3)

    assert first == generate_orders(n_rows=50, random_state=3)
    assert len({o["order_id"] for o in first}) == 50
    assert all(o["express_eligible"] in (0, 1) for o in first)
