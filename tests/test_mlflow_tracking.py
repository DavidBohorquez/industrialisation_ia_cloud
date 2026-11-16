import pytest

# Needs the train extra. The serving CI job runs `pytest -m "not training"`.
pytestmark = pytest.mark.training


def test_training_run_is_recorded_with_card_metrics_and_model(tmp_path, monkeypatch, trained_model):
    # Imported here, not at the top: pytest imports every test file before filtering by marker,
    # and mlflow is not installed in the serving job.
    from mlflow.tracking import MlflowClient

    from livraison_express.infrastructure.mlflow_tracking import (
        EXPERIMENT_NAME,
        MlflowExperimentTracker,
    )

    working_dir = tmp_path / "cwd"
    working_dir.mkdir()
    monkeypatch.chdir(working_dir)
    tracking_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    artifact_location = str(tmp_path / "mlruns")

    run_id = MlflowExperimentTracker(tracking_uri, artifact_location).log_training(
        trained_model, {"random_state": 0}
    )

    client = MlflowClient(tracking_uri)
    run = client.get_run(run_id)
    assert run.data.metrics == trained_model.card.metrics
    assert run.data.params["random_state"] == "0"
    assert run.data.params["model_version"] == "test"
    assert client.get_experiment(run.info.experiment_id).name == EXPERIMENT_NAME
    assert "model_card.json" in {artifact.path for artifact in client.list_artifacts(run_id)}
    assert run.info.artifact_uri.startswith(artifact_location)
    assert not (working_dir / "mlruns").exists()
