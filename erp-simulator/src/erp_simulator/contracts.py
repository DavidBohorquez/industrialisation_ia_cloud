"""Contrats entre l'orchestration (simulator.py) et les bases (storage.py).

Séparés de storage.py : l'orchestration ne dépend que de ces contrats, pas des pilotes
psycopg et pymongo, et se teste donc sans base de données.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Protocol, runtime_checkable

Order = dict[str, object]


class OrderWriter(Protocol):
    def write(self, orders: Sequence[Order]) -> int:
        """Écrit les commandes et renvoie le nombre de nouvelles commandes."""

    def close(self) -> None:
        """Libère les ressources de connexion."""


@runtime_checkable
class OrderCounter(Protocol):
    def count_from(self, start: date, end: date) -> int:
        """Compte les commandes sur une période."""

    def next_sequence(self) -> int:
        """Retourne le prochain numéro de commande disponible."""


@runtime_checkable
class OutcomeSource(Protocol):
    def last_order_date(self) -> date | None:
        """Date de la commande la plus récente : l'horloge simulée, même après un redémarrage."""

    def pending_outcomes(self, known_until: date) -> list[Order]:
        """Commandes sans résultat, datées au plus tard de known_until, dont le résultat
        peut être simulé (preparation_time_min renseigné)."""


@runtime_checkable
class OutcomeWriter(Protocol):
    def set_outcomes(self, outcomes: Mapping[str, int]) -> int:
        """Enregistre les résultats {order_id: 0 ou 1} et renvoie le nombre de commandes mises
        à jour. Un résultat déjà enregistré n'est jamais remplacé."""
