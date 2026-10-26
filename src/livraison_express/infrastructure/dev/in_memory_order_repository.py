from collections.abc import Iterable, Mapping
from typing import Any

from livraison_express.abstractions.order_repository import OrderRepository
from livraison_express.core.features import TARGET_COLUMN


class InMemoryOrderRepository(OrderRepository):
    """Dev and tests only: orders in a dict. Lost on restart, not shared between processes."""

    def __init__(self, orders: Iterable[Mapping[str, Any]] = ()):
        self._orders: dict[str, dict[str, Any]] = {}
        for order in orders:
            self.save(order)

    def save(self, order: Mapping[str, Any]) -> None:
        if "order_id" not in order:
            raise ValueError("Une commande doit avoir un order_id pour être enregistrée.")
        self._orders[order["order_id"]] = dict(order)

    def get(self, order_id: str) -> dict[str, Any] | None:
        order = self._orders.get(order_id)
        return dict(order) if order is not None else None

    def get_all(self) -> list[dict[str, Any]]:
        return [dict(order) for order in self._orders.values()]

    def count(self) -> int:
        return len(self._orders)

    def get_training_data(self) -> list[dict[str, Any]]:
        return [
            dict(order)
            for order in self._orders.values()
            if order.get(TARGET_COLUMN) is not None
        ]
