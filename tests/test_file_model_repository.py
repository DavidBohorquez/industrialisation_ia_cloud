import json

import pytest

from livraison_express.core.predictor import EligibilityPredictor
from livraison_express.infrastructure.dev.file_model_repository import FileModelRepository


def test_saved_model_reloads_with_same_card_and_predictions(tmp_path, trained_model, valid_order):
    repository = FileModelRepository(tmp_path)

    repository.save(trained_model)
    loaded = repository.load("test")

    assert loaded.card == trained_model.card
    assert (
        EligibilityPredictor(loaded).predict_one(valid_order).probability
        == EligibilityPredictor(trained_model).predict_one(valid_order).probability
    )


def test_metadata_file_is_the_model_card(tmp_path, trained_model):
    FileModelRepository(tmp_path).save(trained_model)

    metadata = json.loads((tmp_path / "test" / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["model_version"] == "test"
    assert metadata["model_type"] == "LogisticRegression"
    assert metadata["target"] == "express_eligible"
    assert metadata["evaluation_threshold"] == 0.5
    assert metadata["limitations"]


def test_existing_version_is_never_overwritten(tmp_path, trained_model):
    repository = FileModelRepository(tmp_path)
    repository.save(trained_model)

    with pytest.raises(FileExistsError):
        repository.save(trained_model)


def test_unknown_version_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError, match="9.9.9"):
        FileModelRepository(tmp_path).load("9.9.9")
