import logging

import pandas as pd

from livraison_express.abstractions.experiment_tracker import ExperimentTracker
from livraison_express.abstractions.model_repository import ModelRepository
from livraison_express.abstractions.order_repository import OrderRepository
from livraison_express.core.data_quality import clean_orders_data, validate_dataset
from livraison_express.core.domain import TrainedModel
from livraison_express.core.learning.ml_trainer import MLTrainer

logger = logging.getLogger(__name__)


def run_training(
    order_repository: OrderRepository,
    model_repository: ModelRepository,
    tracker: ExperimentTracker,
    trainer: MLTrainer,
    version: str,
) -> TrainedModel:
    """Training job: labelled orders -> quality checks -> MLTrainer -> model repository -> tracking."""
    records = order_repository.get_training_data()
    if not records:
        raise ValueError("Aucune commande avec un résultat connu : impossible d'entraîner un modèle.")

    orders = clean_orders_data(pd.DataFrame(records))
    validate_dataset(orders)
    logger.info("Données prêtes pour l'entraînement (commandes=%d)", len(orders))

    model = trainer.train(orders, version)
    model_repository.save(model)
    logger.info("Modèle %s enregistré", version)

    # Tracked after saving: a run is never recorded for a model that could not be stored.
    run_id = tracker.log_training(model, trainer.params)
    logger.info("Entraînement suivi dans le run %s", run_id)

    return model
