import pandas as pd
import pytest

from livraison_express.core.predictor import EligibilityPredictor


def test_predict_one_returns_a_valid_prediction(trained_model, valid_order):
    result = EligibilityPredictor(trained_model).predict_one(valid_order)

    assert result.decision in {"oui", "non"}
    assert isinstance(result.express_eligible, bool)
    assert 0 <= result.probability <= 1
    assert result.model_version == "test"


def test_missing_feature_is_rejected(trained_model, valid_order):
    del valid_order["distance_km"]

    with pytest.raises(ValueError, match="distance_km"):
        EligibilityPredictor(trained_model).predict_one(valid_order)


def test_threshold_controls_the_decision(trained_model, valid_order):
    always_yes = EligibilityPredictor(trained_model, threshold=0).predict_one(valid_order)
    always_no = EligibilityPredictor(trained_model, threshold=1).predict_one(valid_order)

    assert always_yes.decision == "oui"
    assert always_no.decision == "non"


@pytest.mark.parametrize("threshold", [-0.1, 1.5])
def test_invalid_threshold_is_rejected(trained_model, threshold):
    with pytest.raises(ValueError, match="seuil"):
        EligibilityPredictor(trained_model, threshold=threshold)


def test_batch_matches_single_predictions(trained_model, valid_order):
    predictor = EligibilityPredictor(trained_model)
    other_order = {**valid_order, "distance_km": 30, "stock_available": 0}

    batch = predictor.predict_batch(pd.DataFrame([valid_order, other_order]))

    assert list(batch["decision"]) == [
        predictor.predict_one(valid_order).decision,
        predictor.predict_one(other_order).decision,
    ]
    assert batch["eligibility_probability"].between(0, 1).all()


def test_predict_many_matches_predict_one(trained_model, valid_order):
    predictor = EligibilityPredictor(trained_model)
    other_order = {**valid_order, "distance_km": 30, "stock_available": 0}

    many = predictor.predict_many([valid_order, other_order])

    assert [p.probability for p in many] == [
        predictor.predict_one(valid_order).probability,
        predictor.predict_one(other_order).probability,
    ]
