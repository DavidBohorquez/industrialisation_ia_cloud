"""Configuration du scénario ERP."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SimulationConfig:
    postgres_dsn: str
    mongo_uri: str
    batch_size: int = 5
    interval_seconds: float = 5.0
    postgres_old_history_orders: int = 10_000
    recent_history_orders: int = 1_000
    live_order_limit: int = 0
    # Jours simulés avant que le résultat d'une commande (express_eligible) soit connu.
    label_delay_days: int = 2
    log_level: str = "INFO"
    today: date = date.today()

    @classmethod
    def from_environment(cls) -> SimulationConfig:
        return cls(
            postgres_dsn=os.environ["POSTGRES_DSN"],
            mongo_uri=os.environ["MONGO_URI"],
            batch_size=int(os.getenv("BATCH_SIZE", "5")),
            interval_seconds=float(os.getenv("INTERVAL_SECONDS", "5")),
            postgres_old_history_orders=int(os.getenv("POSTGRES_HISTORY_ORDERS", "10000")),
            recent_history_orders=int(os.getenv("RECENT_HISTORY_ORDERS", "1000")),
            live_order_limit=int(os.getenv("LIVE_ORDER_LIMIT", "0")),
            label_delay_days=int(os.getenv("LABEL_DELAY_DAYS", "2")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            today=date.today(),
        )
