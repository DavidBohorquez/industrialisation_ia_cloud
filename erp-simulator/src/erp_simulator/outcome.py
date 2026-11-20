"""Résultat simulé d'une commande : la cible express_eligible.

Le sujet ne générait pas la cible. Le professeur a confirmé l'oubli (2026-11-20) et indiqué
l'heuristique de génération du cours (notebook, cellule 8). Elle est reprise ici avec les
mêmes coefficients, la même sigmoïde et le même tirage (Bernoulli de probabilité p),
traduite dans le vocabulaire de l'ERP. Les choix de traduction sont dans le README.

Ce module simule « le monde » : la décision réelle que le modèle devra apprendre. Il vit
dans le simulateur et jamais dans l'application, qui ne voit que des données et des résultats.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from typing import Any

Order = Mapping[str, Any]

# Pénalités et bonus du notebook, traduits dans le vocabulaire de l'ERP.
WEATHER_PENALTY = {"clear": 0.0, "rain": 0.10, "snow": 0.25, "wind": 0.20}
ZONE_PENALTY = {"centre": 0.0, "suburb": 0.175, "rural": 0.45}
CUSTOMER_BONUS = {"individual": 0.0, "business": 0.15}

# Hypothèse : carrier_capacity est une capacité libre sur un maximum de 50.
# Le notebook raisonne en part libre (0-1) : la valeur est divisée par ce maximum.
CARRIER_CAPACITY_MAX = 50.0

# Au-delà de cette heure, chaque heure supplémentaire pénalise la livraison express.
LATE_HOUR = 18


def eligibility_score(order: Order) -> float:
    """Score latent du notebook : plus il est élevé, plus la livraison express est probable."""
    capacity = float(order["carrier_capacity"])
    if not 0 <= capacity <= CARRIER_CAPACITY_MAX:
        raise ValueError(
            f"carrier_capacity={capacity} sort de l'hypothèse 0-{CARRIER_CAPACITY_MAX:g} : "
            "la conversion en part libre n'est plus valable."
        )
    # Le vrai jour de la semaine, même quand la colonne weekend vaut NULL (avant juillet 2015) :
    # la colonne manque dans la base, pas dans la réalité.
    weekend = int(order["day_of_week"] >= 5)

    return (
        2.5
        - 0.18 * order["distance_km"]
        - 0.035 * order["preparation_time_min"]
        - 0.035 * order["weight_kg"]
        - _lookup(ZONE_PENALTY, order, "delivery_zone")
        - _lookup(WEATHER_PENALTY, order, "weather")
        + 1.8 * order["stock_available"]
        + 1.3 * capacity / CARRIER_CAPACITY_MAX
        + _lookup(CUSTOMER_BONUS, order, "customer_type")
        - 0.40 * weekend
        - 0.08 * max(order["hour"] - LATE_HOUR, 0)
    )


def eligibility_probability(order: Order) -> float:
    """Sigmoïde du score : la probabilité que la commande soit éligible."""
    return 1 / (1 + math.exp(-eligibility_score(order)))


def express_eligible(order: Order) -> int | None:
    """1 si la commande est éligible, 0 sinon, None si son résultat ne peut pas être simulé.

    preparation_time_min vaut NULL avant juillet 2017 : sans lui la décision ne peut pas
    être calculée, et l'imputer reviendrait à fabriquer une étiquette.
    """
    if order.get("preparation_time_min") is None:
        return None

    # Une graine par commande : la même commande reçoit toujours le même résultat, dans
    # n'importe quel processus. Une graine str est stable, contrairement à hash().
    draw = random.Random(f"outcome:{order['order_id']}").random()
    return int(draw < eligibility_probability(order))


def _lookup(table: Mapping[str, float], order: Order, field: str) -> float:
    value = order[field]
    try:
        return table[value]
    except KeyError:
        raise ValueError(
            f"Valeur inconnue pour {field} : {value!r} (attendu : {', '.join(table)})."
        ) from None
