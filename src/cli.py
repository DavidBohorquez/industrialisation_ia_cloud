import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from src.config import Settings, load_settings
from src.core.predictor import EligibilityPredictor
from src.core.training import run_training
from src.factory import build_model_repository, build_order_source


def train(settings: Settings) -> None:
    model = run_training(
        source=build_order_source(settings),
        repository=build_model_repository(settings),
        version=settings.model_version,
        random_state=settings.random_state,
    )

    print(f"Modèle {model.version} entraîné et enregistré dans {settings.artifacts_dir}.")
    for metric_name, metric_value in model.metrics.items():
        print(f"{metric_name:>10} : {metric_value:.4f}")


def predict(settings: Settings, order_file: Path) -> None:
    order = json.loads(order_file.read_text(encoding="utf-8"))

    if not isinstance(order, dict):
        raise ValueError("Le fichier doit contenir un objet JSON décrivant une commande.")

    prediction = _load_predictor(settings).predict_one(order)
    print(json.dumps(prediction.to_dict(), indent=2, ensure_ascii=False))


def predict_batch(settings: Settings, input_file: Path, output_file: Path) -> None:
    predictions = _load_predictor(settings).predict_batch(pd.read_csv(input_file))
    predictions.to_csv(output_file, index=False)

    print(f"{len(predictions)} prédictions enregistrées dans {output_file}.")


def _load_predictor(settings: Settings) -> EligibilityPredictor:
    model = build_model_repository(settings).load(settings.model_version)
    return EligibilityPredictor(model, threshold=settings.decision_threshold)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src",
        description="Éligibilité d'une commande à la livraison express.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

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

        if args.command == "train":
            train(settings)
        elif args.command == "predict":
            predict(settings, args.order_file)
        else:
            predict_batch(settings, args.input_file, args.output_file)
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1

    return 0
