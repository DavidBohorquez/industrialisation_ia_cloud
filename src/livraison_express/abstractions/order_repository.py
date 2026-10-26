from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class OrderRepository(ABC):
    """Where the application keeps orders: plain dicts keyed by field name (ADR-0005).

    Contract every implementation must respect (checked by tests/test_order_repository.py):
    - an order must contain "order_id"; saving the same id again replaces it (no duplicate);
    - `get` returns None for an unknown id, it does not raise;
    - returned orders are copies: changing them does not change what is stored.
    """

    @abstractmethod
    def save(self, order: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get(self, order_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def get_all(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def get_training_data(self) -> list[dict[str, Any]]:
        """Orders whose outcome (express_eligible) is known, in a stable order."""
