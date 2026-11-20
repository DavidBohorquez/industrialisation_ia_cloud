"""Orchestration du scénario ERP."""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta

from config import SimulationConfig
from contracts import OrderCounter, OrderWriter, OutcomeSource, OutcomeWriter
from generator import OrderGenerator
from outcome import express_eligible


class ErpSimulator:
    def __init__(
        self,
        config: SimulationConfig,
        generator: OrderGenerator,
        postgres: OrderWriter,
        mongo: OrderWriter,
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.generator = generator
        self.postgres = postgres
        self.mongo = mongo
        self.logger = logger

    def run(self) -> None:
        try:
            self._write_history()
            self._resolve_outcomes(self._last_order_date())
            self._write_live_stream()
        finally:
            self.postgres.close()
            self.mongo.close()
            self.logger.info("Connexions aux bases fermées.")

    def _write_history(self) -> None:
        old_count = self.config.postgres_old_history_orders
        recent_count = self.config.recent_history_orders
        old_orders = self.generator.old_history(old_count, self.config.today, first_sequence=1)
        self.logger.info("Ancien historique PostgreSQL : %d commandes.", self.postgres.write(old_orders))

        recent_orders = self.generator.recent_history(
            recent_count, self.config.today, first_sequence=old_count + 1
        )
        self.logger.info("Historique partagé 2023+ PostgreSQL : %d commandes.", self.postgres.write(recent_orders))
        self.logger.info("Historique partagé 2023+ MongoDB : %d commandes.", self.mongo.write(recent_orders))

        if isinstance(self.postgres, OrderCounter):
            count = self.postgres.count_from(date(2023, 1, 1), self.config.today)
            self.logger.info("PostgreSQL : %d commandes présentes depuis 2023.", count)

    def _write_live_stream(self) -> None:
        minimum_sequence = (
            self.config.postgres_old_history_orders
            + self.config.recent_history_orders
            + 1
        )
        sequence = minimum_sequence
        if isinstance(self.postgres, OrderCounter):
            sequence = max(sequence, self.postgres.next_sequence() + 1)
            self.logger.info("Prochaine séquence live : ERP-%08d.", sequence)
        simulation_date = self._first_live_date()
        while self.config.live_order_limit == 0 or sequence <= self.config.live_order_limit:
            size = self._next_batch_size(sequence)
            orders = self.generator.live_batch(sequence, size, simulation_date)
            postgres_count = self.postgres.write(orders)
            mongo_count = self.mongo.write(orders)
            self.logger.info(
                "Lot live : PostgreSQL=%d, MongoDB=%d, date=%s, dernière commande=%s.",
                postgres_count,
                mongo_count,
                orders[-1]["order_date"],
                orders[-1]["order_id"],
            )
            if isinstance(self.postgres, OrderCounter):
                next_day = simulation_date + timedelta(days=1)
                count = self.postgres.count_from(simulation_date, next_day)
                self.logger.info(
                    "PostgreSQL : %d commandes présentes pour la date live %s.",
                    count,
                    simulation_date,
                )
            self._resolve_outcomes(simulation_date)
            sequence += size
            simulation_date += timedelta(days=1)
            time.sleep(self.config.interval_seconds)
        self.logger.info("Flux live terminé : limite LIVE_ORDER_LIMIT atteinte.")

    def _next_batch_size(self, sequence: int) -> int:
        remaining = self.config.live_order_limit - sequence + 1
        return min(self.config.batch_size, remaining) if self.config.live_order_limit else self.config.batch_size

    def _last_order_date(self) -> date | None:
        if isinstance(self.postgres, OutcomeSource):
            return self.postgres.last_order_date()
        return None

    def _first_live_date(self) -> date:
        """Date du premier lot live : le lendemain de la dernière date simulée.

        Le sujet repartait toujours d'aujourd'hui ; après un redémarrage, l'horloge simulée
        aurait reculé et plus aucun résultat n'aurait été révélé avant de la rattraper.
        """
        last_date = self._last_order_date()
        if last_date is None:
            return self.config.today
        return max(self.config.today, last_date + timedelta(days=1))

    def _resolve_outcomes(self, clock: date | None) -> None:
        """Révèle le résultat des commandes datées d'au moins LABEL_DELAY_DAYS jours simulés.

        L'horloge est la date simulée la plus récente : chaque lot live avance d'un jour.
        """
        if clock is None or not isinstance(self.postgres, OutcomeSource):
            return
        known_until = clock - timedelta(days=self.config.label_delay_days)
        outcomes: dict[str, int] = {}
        for order in self.postgres.pending_outcomes(known_until):
            outcome = express_eligible(order)
            if outcome is not None:
                outcomes[str(order["order_id"])] = outcome
        if not outcomes:
            return

        counts = [
            writer.set_outcomes(outcomes) if isinstance(writer, OutcomeWriter) else 0
            for writer in (self.postgres, self.mongo)
        ]
        self.logger.info(
            "Résultats connus jusqu'au %s : PostgreSQL=%d, MongoDB=%d, éligibles=%.0f %%.",
            known_until,
            counts[0],
            counts[1],
            100 * sum(outcomes.values()) / len(outcomes),
        )
