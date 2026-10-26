from pathlib import Path

import pytest
from pydantic import ValidationError

from livraison_express.config import PROJECT_ROOT, Settings

ENV_KEYS = [
    "APP_ENV",
    "ARTIFACTS_DIR",
    "MODEL_VERSION",
    "DECISION_THRESHOLD",
    "RANDOM_STATE",
    "LOG_LEVEL",
    "MLFLOW_TRACKING_URI",
    "MLFLOW_ARTIFACT_LOCATION",
]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_without_environment():
    settings = Settings(_env_file=None)

    assert settings.environment == "dev"
    assert settings.artifacts_dir == PROJECT_ROOT / "artifacts"
    assert settings.model_version == "1.0.0"
    assert settings.decision_threshold == 0.5
    assert settings.random_state == 42
    assert settings.log_level == "INFO"
    assert settings.mlflow_tracking_uri == f"sqlite:///{PROJECT_ROOT / 'mlflow.db'}"
    assert settings.mlflow_artifact_location == str(PROJECT_ROOT / "mlruns")


def test_environment_variables_override_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DECISION_THRESHOLD", "0.7")
    monkeypatch.setenv("ARTIFACTS_DIR", "/srv/models")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.decision_threshold == 0.7
    assert settings.artifacts_dir == Path("/srv/models")


def test_env_file_is_read_and_environment_wins(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_VERSION=2.0.0\nLOG_LEVEL=DEBUG\n", encoding="utf-8")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    settings = Settings(_env_file=env_file)

    assert settings.model_version == "2.0.0"
    assert settings.log_level == "WARNING"


def test_empty_value_means_default(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ARTIFACTS_DIR=\nDECISION_THRESHOLD=\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.artifacts_dir == PROJECT_ROOT / "artifacts"
    assert settings.decision_threshold == 0.5


def test_env_example_is_a_valid_configuration():
    Settings(_env_file=PROJECT_ROOT / ".env.example")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("DECISION_THRESHOLD", "abc"),
        ("DECISION_THRESHOLD", "1.5"),
        ("RANDOM_STATE", "forty-two"),
        ("LOG_LEVEL", "VERBOSE"),
    ],
)
def test_invalid_value_fails_at_startup(monkeypatch, key, value):
    monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError, match=key.lower()):
        Settings(_env_file=None)


def test_settings_are_immutable():
    settings = Settings(_env_file=None)

    with pytest.raises(ValidationError):
        settings.decision_threshold = 0.9
