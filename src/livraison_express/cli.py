import argparse
import json
import logging
from pathlib import Path

import pandas as pd
import uvicorn

from livraison_express.config import Settings, load_settings
from livraison_express.core.training import run_training
from livraison_express.factory import build_model_repository, build_order_source, build_predictor
from livraison_express.logging_config import configure_logging

logger = logging.getLogger(__name__)


def train(settings: Settings) -> None:
    model = run_training(
        source=build_order_source(settings),
        repository=build_model_repository(settings),
        version=settings.model_version,
        random_state=settings.random_state,
    )

    logger.info("Modèle %s entraîné et enregistré dans %s.", model.version, settings.artifacts_dir)
    for metric_name, metric_value in model.metrics.items():
        logger.info("%10s : %.4f", metric_name, metric_value)


def predict(settings: Settings, order_file: Path) -> None:
    order = json.loads(order_file.read_text(encoding="utf-8"))

    if not isinstance(order, dict):
        raise ValueError("Le fichier doit contenir un objet JSON décrivant une commande.")

    prediction = build_predictor(settings).predict_one(order)
    print(json.dumps(prediction.to_dict(), indent=2, ensure_ascii=False))


def predict_batch(settings: Settings, input_file: Path, output_file: Path) -> None:
    predictions = build_predictor(settings).predict_batch(pd.read_csv(input_file))
    predictions.to_csv(output_file, index=False)

    logger.info("%d prédictions enregistrées dans %s.", len(predictions), output_file)


def serve(host: str, port: int) -> None:
    # Import string, not an app object: uvicorn builds the app itself (needed for reload/workers).
    uvicorn.run("livraison_express.api.main:app", host=host, port=port)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m livraison_express",
        description="Éligibilité d'une commande à la livraison express.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    serve_parser = commands.add_parser("serve", help="Démarrer l'API HTTP.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Adresse d'écoute (défaut : %(default)s).")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port d'écoute (défaut : %(default)s).")

    commands.add_parser("train", help="Entraîner et enregistrer le modèle.")

    predict_parser = commands.add_parser("predict", help="Prédire pour une commande (JSON).")
    predict_parser.add_argument("order_file", type=Path)

    batch_parser = commands.add_parser("predict-batch", help="Prédire pour un fichier CSV.")
    batch_parser.add_argument("input_file", type=Path)
    batch_parser.add_argument("output_file", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        settings = load_settings()
        configure_logging(settings.log_level)

        if args.command == "serve":
            serve(args.host, args.port)
        elif args.command == "train":
            train(settings)
        elif args.command == "predict":
            predict(settings, args.order_file)
        else:
            predict_batch(settings, args.input_file, args.output_file)
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        logger.error("Erreur : %s", error)
        return 1

    return 0
