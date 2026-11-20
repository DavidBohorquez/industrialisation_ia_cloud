from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class OrderReader(ABC):
    """Read access to orders: plain dicts keyed by field name, canonical vocabulary (ADR-0005).

    Code that only reads orders (training, scoring) depends on this interface, so it can be
    given a source the application must never write to, such as the company's ERP (ADR-0012).

    Contract every implementation must respect (checked by tests/test_order_repository.py):
    - `get` returns None for an unknown id, it does not raise;
    - `get_all` and `get_training_data` are sorted by order_id, so the same orders give the
      same training set (and the same model) whatever the store;
    - returned orders are copies: changing them does not change what is stored;
    - an implementation that translates a foreign format may skip a record it cannot translate
      (logged as a warning). `count` still counts it: comparing `count()` with
      `len(get_all())` shows how many records were skipped.
    """

    @abstractmethod
    def get(self, order_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def get_all(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def count(self) -> int:
        """Number of orders held by the store."""

    @abstractmethod
    def get_training_data(self) -> list[dict[str, Any]]:
        """Orders whose outcome (express_eligible) is known, sorted by order_id."""


class OrderWriter(ABC):
    """Write access to orders. Only stores the application owns implement it (ADR-0012)."""

    @abstractmethod
    def save(self, order: Mapping[str, Any]) -> None:
        """Store an order. It must contain "order_id"; saving the same id again replaces it."""


class OrderRepository(OrderReader, OrderWriter):
    """Read and write access: a store the application owns (the course's `OrderRepository`)."""
