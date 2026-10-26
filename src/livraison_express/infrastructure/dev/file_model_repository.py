import json
from pathlib import Path

import joblib

from livraison_express.abstractions.model_repository import ModelRepository
from livraison_express.core.domain import TrainedModel

MODEL_FILE = "model.joblib"
METADATA_FILE = "metadata.json"


class FileModelRepository(ModelRepository):
    """Stockage dans un répertoire local, un sous-dossier par version (ADR-0000)."""

    def __init__(self, base_dir: Path):
        self._base_dir = Path(base_dir)

    def save(self, model: TrainedModel) -> None:
        version_dir = self._base_dir / model.version

        if version_dir.exists():
            raise FileExistsError(
                f"La version {model.version} existe déjà dans {version_dir}. "
                "Changer MODEL_VERSION pour enregistrer un nouveau modèle."
            )

        version_dir.mkdir(parents=True)
        joblib.dump(model.pipeline, version_dir / MODEL_FILE)

        metadata = {
            "version": model.version,
            "features": model.features,
            "metrics": model.metrics,
            "trained_at": model.trained_at,
        }
        (version_dir / METADATA_FILE).write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

    def load(self, version: str) -> TrainedModel:
        version_dir = self._base_dir / version

        if not version_dir.exists():
            raise FileNotFoundError(
                f"Aucun modèle pour la version {version} dans {self._base_dir}. "
                "Lancer d'abord l'entraînement."
            )

        metadata = json.loads((version_dir / METADATA_FILE).read_text(encoding="utf-8"))

        return TrainedModel(
            pipeline=joblib.load(version_dir / MODEL_FILE),
            version=metadata["version"],
            features=metadata["features"],
            metrics=metadata["metrics"],
            trained_at=metadata["trained_at"],
        )
