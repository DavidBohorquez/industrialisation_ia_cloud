import json

import uvicorn

from livraison_express import cli
from livraison_express.core.predictor import EligibilityPredictor


def test_serve_starts_uvicorn_with_the_api(monkeypatch):
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **options: calls.append((app, options)))

    exit_code = cli.main(["serve", "--host", "0.0.0.0", "--port", "9000"])

    assert exit_code == 0
    assert calls == [("livraison_express.api.main:app", {"host": "0.0.0.0", "port": 9000})]


def test_serve_defaults_to_localhost(monkeypatch):
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **options: calls.append(options))

    cli.main(["serve"])

    assert calls == [{"host": "127.0.0.1", "port": 8000}]


def test_predict_prints_the_prediction_as_json(tmp_path, monkeypatch, capsys, trained_model, valid_order):
    order_file = tmp_path / "order.json"
    order_file.write_text(json.dumps(valid_order), encoding="utf-8")
    monkeypatch.setattr(cli, "build_predictor", lambda settings: EligibilityPredictor(trained_model))

    exit_code = cli.main(["predict", str(order_file)])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["decision"] in {"oui", "non"}


def test_invalid_order_file_returns_exit_code_1(tmp_path):
    order_file = tmp_path / "order.json"
    order_file.write_text("[1, 2, 3]", encoding="utf-8")

    assert cli.main(["predict", str(order_file)]) == 1
