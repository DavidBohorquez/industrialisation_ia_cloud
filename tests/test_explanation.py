import math

import pandas as pd

from livraison_express.core.domain import Factor, Prediction
from livraison_express.core.explanation import TemplateExplanationGenerator, linear_contributions
from livraison_express.core.features import FEATURE_COLUMNS
from livraison_express.core.predictor import EligibilityPredictor


def make_prediction(eligible: bool, probability: float) -> Prediction:
    return Prediction(
        express_eligible=eligible,
        decision="oui" if eligible else "non",
        probability=probability,
        model_version="test",
        prediction_timestamp="2026-10-09T00:00:00+00:00",
    )


def test_contributions_cover_each_feature_once(trained_model, valid_order):
    factors = linear_contributions(trained_model.pipeline, pd.DataFrame([valid_order]))

    assert sorted(f.feature for f in factors) == sorted(FEATURE_COLUMNS)


def test_contributions_add_up_to_the_model_score(trained_model, valid_order):
    predictor = EligibilityPredictor(trained_model)
    classifier = trained_model.pipeline.named_steps["classifier"]

    factors = linear_contributions(trained_model.pipeline, pd.DataFrame([valid_order]))
    score = sum(f.contribution for f in factors) + classifier.intercept_[0]
    probability = 1 / (1 + math.exp(-score))

    assert math.isclose(probability, predictor.predict_one(valid_order).probability, abs_tol=1e-4)


def test_long_distance_is_a_top_unfavorable_factor(trained_model, valid_order):
    far_order = {**valid_order, "distance_km": 45}

    factors = EligibilityPredictor(trained_model).top_factors(far_order)

    distance = next(f for f in factors if f.feature == "distance_km")
    assert distance.contribution < 0


def test_template_text_states_the_decision_and_reasons(valid_order):
    factors = [Factor("distance_km", 1.2), Factor("weather", -0.4)]

    text = TemplateExplanationGenerator().explain(make_prediction(True, 0.94), factors, valid_order)

    assert text.startswith("Cette commande est éligible")
    assert "94 %" in text
    assert "en sa faveur : la distance (2 km)" in text
    assert "joue contre : la météo (normal)" in text


def test_template_formats_values_for_french_readers(valid_order):
    order = {**valid_order, "distance_km": 28.0, "carrier_capacity": 0.85}
    factors = [Factor("distance_km", -2.0), Factor("carrier_capacity", -0.5)]

    text = TemplateExplanationGenerator().explain(make_prediction(False, 0.0007), factors, order)

    assert "moins de 1 %" in text
    assert "la distance (28 km)" in text
    assert "la capacité du transporteur (0,85)" in text


def test_template_never_contradicts_the_decision(valid_order):
    factors = [Factor("stock_available", 2.0)]

    text = TemplateExplanationGenerator().explain(make_prediction(False, 0.31), factors, valid_order)

    assert "n'est pas éligible" in text
