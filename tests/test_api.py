import pytest
from fastapi.testclient import TestClient

from livraison_express.api.app import MAX_BATCH_SIZE, create_app
from livraison_express.core.explanation import TemplateExplanationGenerator
from livraison_express.core.predictor import EligibilityPredictor


@pytest.fixture
def client(trained_model):
    return TestClient(create_app(EligibilityPredictor(trained_model), TemplateExplanationGenerator()))


@pytest.fixture
def client_without_model():
    return TestClient(create_app(None, TemplateExplanationGenerator()))


def error_fields(response) -> list[str]:
    return [error["loc"][-1] for error in response.json()["detail"]]


def test_prediction_with_explanation(client, valid_order):
    response = client.post("/v1/predictions", json=valid_order)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] in {"oui", "non"}
    assert body["model_version"] == "test"
    assert body["explanation"]["source"] == "template"
    assert body["explanation"]["text"].startswith("Cette commande")
    assert len(body["explanation"]["top_factors"]) == 3


def test_explanation_can_be_disabled(client, valid_order):
    response = client.post("/v1/predictions", params={"explain": "false"}, json=valid_order)

    assert response.json()["explanation"] is None


def test_missing_field_is_named(client, valid_order):
    del valid_order["distance_km"]

    response = client.post("/v1/predictions", json=valid_order)

    assert response.status_code == 422
    assert error_fields(response) == ["distance_km"]


def test_out_of_range_value_is_explained(client, valid_order):
    response = client.post("/v1/predictions", json={**valid_order, "carrier_capacity": 1.4})

    error = response.json()["detail"][0]
    assert response.status_code == 422
    assert error["loc"][-1] == "carrier_capacity"
    assert error["input"] == 1.4
    assert "less than or equal to 1" in error["msg"]


def test_unknown_category_lists_allowed_values(client, valid_order):
    response = client.post("/v1/predictions", json={**valid_order, "weather": "brouillard"})

    assert response.status_code == 422
    assert "'normal', 'pluie', 'neige' or 'orage'" in response.json()["detail"][0]["msg"]


def test_unknown_field_is_rejected(client, valid_order):
    response = client.post("/v1/predictions", json={**valid_order, "distanse_km": 3})

    assert response.status_code == 422
    assert error_fields(response) == ["distanse_km"]


def test_inconsistent_weekend_is_explained(client, valid_order):
    response = client.post("/v1/predictions", json={**valid_order, "day_of_week": 6, "weekend": 0})

    assert response.status_code == 422
    assert "weekend must be 1" in response.json()["detail"][0]["msg"]


def test_batch_returns_one_prediction_per_order(client, valid_order):
    far_order = {**valid_order, "distance_km": 40, "stock_available": 0}

    response = client.post("/v1/predictions/batch", json={"orders": [valid_order, far_order]})

    predictions = response.json()["predictions"]
    assert response.status_code == 200
    assert len(predictions) == 2
    assert all(p["explanation"] is None for p in predictions)


def test_batch_too_large_is_rejected_with_413(client, valid_order):
    orders = [valid_order] * (MAX_BATCH_SIZE + 1)

    response = client.post("/v1/predictions/batch", json={"orders": orders})

    assert response.status_code == 413
    assert response.json()["detail"] == (
        f"Batch limited to {MAX_BATCH_SIZE} orders (received {MAX_BATCH_SIZE + 1})."
    )


def test_health_and_model_info(client):
    assert client.get("/health").json() == {"status": "ok", "model_version": "test"}

    info = client.get("/v1/model").json()
    assert info["version"] == "test"
    assert info["decision_threshold"] == 0.5
    assert "roc_auc" in info["metrics"]


def test_without_model_every_endpoint_reports_503(client_without_model, valid_order):
    assert client_without_model.get("/health").status_code == 503
    assert client_without_model.get("/v1/model").status_code == 503

    response = client_without_model.post("/v1/predictions", json=valid_order)
    assert response.status_code == 503
    assert "no model is loaded" in response.json()["detail"]


def test_unexpected_error_hides_internals(trained_model, valid_order):
    class BrokenPredictor(EligibilityPredictor):
        def predict_one(self, order):
            raise RuntimeError("secret: /srv/models/1.0.0/model.joblib is corrupted")

    client = TestClient(
        create_app(BrokenPredictor(trained_model), TemplateExplanationGenerator()),
        raise_server_exceptions=False,
    )

    response = client.post("/v1/predictions", json=valid_order)

    assert response.status_code == 500
    assert response.json()["reference"]
    assert "secret" not in response.text


def test_openapi_contract_lists_the_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths) == {"/health", "/v1/model", "/v1/predictions", "/v1/predictions/batch"}


def test_committed_openapi_file_is_up_to_date():
    from livraison_express.api.export_openapi import OPENAPI_FILE, render_openapi

    assert OPENAPI_FILE.read_text(encoding="utf-8") == render_openapi(), (
        "docs/openapi.json is outdated: run python -m livraison_express.api.export_openapi"
    )
