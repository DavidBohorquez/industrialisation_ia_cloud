import pytest

from livraison_express.core.predictor import EligibilityPredictor
from livraison_express.infrastructure.dev.file_model_repository import FileModelRepository


def test_saved_model_reloads_with_same_predictions(tmp_path, trained_model, valid_order):
    repository = FileModelRepository(tmp_path)

    repository.save(trained_model)
    loaded = repository.load("test")

    assert loaded.version == trained_model.version
    assert loaded.features == trained_model.features
    assert loaded.metrics == trained_model.metrics
    assert (
        EligibilityPredictor(loaded).predict_one(valid_order).probability
        == EligibilityPredictor(trained_model).predict_one(valid_order).probability
    )


def test_existing_version_is_never_overwritten(tmp_path, trained_model):
    repository = FileModelRepository(tmp_path)
    repository.save(trained_model)

    with pytest.raises(FileExistsError):
        repository.save(trained_model)


def test_unknown_version_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError, match="9.9.9"):
        FileModelRepository(tmp_path).load("9.9.9")
