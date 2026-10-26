from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

import mlflow
import mlflow.sklearn

from livraison_express.abstractions.experiment_tracker import ExperimentTracker
from livraison_express.core.domain import TrainedModel

EXPERIMENT_NAME = "livraison-express"


class MlflowExperimentTracker(ExperimentTracker):
    """Suivi des entraînements dans MLflow (local en dev, serveur MLflow plus tard)."""

    def __init__(
        self,
        tracking_uri: str,
        artifact_location: str,
        experiment_name: str = EXPERIMENT_NAME,
    ):
        self._tracking_uri = tracking_uri
        self._artifact_location = artifact_location
        self._experiment_name = experiment_name

    def log_training(self, model: TrainedModel, params: Mapping[str, Any]) -> str:
        mlflow.set_tracking_uri(self._tracking_uri)
        experiment_id = self._experiment_id()
        card = model.card

        with mlflow.start_run(
            experiment_id=experiment_id,
            run_name=f"{card.model_type}-{card.model_version}",
        ) as run:
            mlflow.log_params(
                {
                    **params,
                    "model_version": card.model_version,
                    "model_type": card.model_type,
                    "evaluation_threshold": card.evaluation_threshold,
                    "feature_count": len(card.features),
                }
            )
            mlflow.log_metrics(card.metrics)
            mlflow.log_dict(asdict(card), "model_card.json")
            # skops only reloads allow-listed types; the OneHotEncoder stores a numpy.dtype (data only).
            mlflow.sklearn.log_model(
                model.pipeline, name="model", skops_trusted_types=["numpy.dtype"]
            )
            return run.info.run_id

    def _experiment_id(self) -> str:
        # Without an explicit artifact location, MLflow writes the model files under ./mlruns
        # relative to the current directory, whatever the tracking URI says.
        experiment = mlflow.get_experiment_by_name(self._experiment_name)
        if experiment is not None:
            return experiment.experiment_id
        return mlflow.create_experiment(
            self._experiment_name, artifact_location=self._artifact_location
        )
