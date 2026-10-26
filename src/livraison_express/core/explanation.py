from collections.abc import Mapping
from typing import Any

import pandas as pd
from sklearn.pipeline import Pipeline

from livraison_express.abstractions.explanation_generator import ExplanationGenerator
from livraison_express.core.domain import Factor, Prediction
from livraison_express.core.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES

FEATURE_LABELS = {
    "hour": "l'heure de commande",
    "day_of_week": "le jour",
    "weekend": "la période",
    "distance_km": "la distance",
    "order_value_eur": "le montant",
    "weight_kg": "le poids",
    "stock_available": "le stock",
    "preparation_time_min": "le temps de préparation",
    "carrier_capacity": "la capacité du transporteur",
    "weather": "la météo",
    "delivery_zone": "la zone de livraison",
    "customer_type": "le type de client",
}

UNITS = {
    "distance_km": "km",
    "order_value_eur": "€",
    "weight_kg": "kg",
    "preparation_time_min": "min",
}

DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def linear_contributions(pipeline: Pipeline, data: pd.DataFrame) -> list[Factor]:
    """Contributions exactes d'une régression logistique : coefficient x valeur transformée."""
    preprocessor = pipeline.named_steps["preprocessor"]
    classifier = pipeline.named_steps["classifier"]

    contributions = preprocessor.transform(data)[0] * classifier.coef_[0]

    totals: dict[str, float] = {}
    for column, contribution in zip(preprocessor.get_feature_names_out(), contributions):
        feature = _source_feature(column)
        totals[feature] = totals.get(feature, 0.0) + float(contribution)

    return sorted(
        (Factor(feature, contribution) for feature, contribution in totals.items()),
        key=lambda factor: abs(factor.contribution),
        reverse=True,
    )


def _source_feature(column: str) -> str:
    # "numeric__distance_km" -> "distance_km", "categorical__weather_orage" -> "weather"
    name = column.split("__", 1)[1]
    if name in NUMERIC_FEATURES:
        return name
    return next(feature for feature in CATEGORICAL_FEATURES if name.startswith(f"{feature}_"))


class TemplateExplanationGenerator(ExplanationGenerator):
    """Phrase déterministe au format d'une réponse LLM ; sert aussi de repli si un LLM échoue."""

    source = "template"

    def explain(
        self,
        prediction: Prediction,
        factors: list[Factor],
        order: Mapping[str, Any],
    ) -> str:
        verdict = "est éligible" if prediction.express_eligible else "n'est pas éligible"
        text = (
            f"Cette commande {verdict} à la livraison express "
            f"(probabilité estimée : {_format_probability(prediction.probability)})."
        )

        favorable = [_describe(f.feature, order) for f in factors if f.contribution > 0]
        unfavorable = [_describe(f.feature, order) for f in factors if f.contribution < 0]

        if favorable:
            text += f" Ce qui joue en sa faveur : {_join(favorable)}."
        if unfavorable:
            text += f" Ce qui joue contre : {_join(unfavorable)}."

        return text


def _describe(feature: str, order: Mapping[str, Any]) -> str:
    return f"{FEATURE_LABELS[feature]} ({_format_value(feature, order[feature])})"


def _format_value(feature: str, value: Any) -> str:
    if feature == "day_of_week":
        return DAYS[int(value)]
    if feature == "weekend":
        return "week-end" if value else "semaine"
    if feature == "stock_available":
        return "disponible" if value else "indisponible"
    if feature == "hour":
        return f"{value} h"
    text = _format_number(value) if isinstance(value, int | float) else str(value)
    unit = UNITS.get(feature)
    return f"{text} {unit}" if unit else text


def _format_probability(probability: float) -> str:
    if probability < 0.01:
        return "moins de 1 %"
    if probability > 0.99:
        return "plus de 99 %"
    return f"{round(probability * 100)} %"


def _format_number(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} et {parts[-1]}"
