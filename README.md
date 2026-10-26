# Express Delivery Eligibility

Predicts whether an order can be delivered express (same day), as a decision aid alongside business rules.

This project turns an experimental Jupyter notebook into a production-ready Python application. It is the practical work for the course *Industrialisation de l'IA dans le cloud* (YNOV Toulouse, M2 Data & IA).

## Problem

| | |
|---|---|
| Task | Binary classification |
| Target | `express_eligible` (1 = eligible, 0 = not eligible) |
| Model | Logistic regression (scikit-learn pipeline) |
| Data | Synthetic orders in the dev environment |

Features used by the model:

- **Order:** `hour`, `day_of_week`, `weekend`, `order_value_eur`, `weight_kg`, `customer_type`
- **Logistics:** `distance_km`, `delivery_zone`, `carrier_capacity`, `weather`
- **Warehouse:** `stock_available`, `preparation_time_min`

## Getting started

Requirements: Python 3.13+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt    # tests and notebook tools (includes requirements.txt)
pip install -e .                       # installs the livraison_express package in editable mode
python -m livraison_express train      # train model MODEL_VERSION (needed once)
```

## HTTP API

```bash
uvicorn livraison_express.api.main:app --reload      # http://127.0.0.1:8000
```

- Swagger UI (try the endpoints in the browser): http://127.0.0.1:8000/docs
- OpenAPI contract: http://127.0.0.1:8000/openapi.json, with a committed copy in [`docs/openapi.json`](docs/openapi.json)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/predictions` | One order -> prediction + explanation (`?explain=false` to skip it) |
| `POST` | `/v1/predictions/batch` | `{"orders": [...]}`, up to 1000 orders (`?explain=true` to add explanations) |
| `GET` | `/v1/model` | Loaded model: version, training date, threshold, features, metrics |
| `GET` | `/health` | Liveness: always `200` while the process runs |
| `GET` | `/health/ready` | Readiness: `200` when a model is loaded, `503` otherwise |

Example:

```bash
curl -X POST http://127.0.0.1:8000/v1/predictions \
     -H "Content-Type: application/json" -d @examples/order.json
```

```json
{
  "express_eligible": true,
  "decision": "oui",
  "probability": 0.9377,
  "model_version": "1.0.0",
  "prediction_timestamp": "2026-10-09T10:16:37.615812+00:00",
  "explanation": {
    "text": "Cette commande est éligible à la livraison express (probabilité estimée : 94 %). Ce qui joue en sa faveur : la distance (3,5 km), la capacité du transporteur (0,85) et le poids (2,4 kg).",
    "source": "template",
    "top_factors": ["distance_km", "carrier_capacity", "weight_kg"]
  }
}
```

The explanation text is generated from the model's exact contributions by a template today (`"source": "template"`). An LLM generator can replace it later without changing this contract (see ADR-0003).

Errors:

| Code | When | Body |
|---|---|---|
| `422` | Missing field, value out of range, unknown category or field, `weekend` inconsistent with `day_of_week` | Every problem at once, with field, received value and rule |
| `413` | Batch over 1000 orders | `Batch limited to 1000 orders (received N).` |
| `503` | No model loaded | `Prediction service temporarily unavailable: no model is loaded.` |
| `500` | Unexpected error | Generic message + `reference`; details only in server logs |

## Command line

```bash
python -m livraison_express train                                         # train and save model MODEL_VERSION
python -m livraison_express predict examples/order.json                   # one order -> JSON result
python -m livraison_express predict-batch examples/orders.csv out.csv     # CSV of orders -> CSV with predictions
python -m livraison_express.api.export_openapi                            # regenerate docs/openapi.json
python -m pytest                                            # run the tests
```

## Configuration

Settings are read by `src/livraison_express/config.py` (`pydantic-settings`), in this priority order: environment variables, then a `.env` file at the project root, then the defaults below. Copy `.env.example` to `.env` to change them locally. Invalid values (e.g. `DECISION_THRESHOLD=abc`) stop the program at startup with a clear message.

| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | `dev` | Selects the implementations in `src/livraison_express/factory.py` |
| `ARTIFACTS_DIR` | `<project>/artifacts` | Where model versions are stored |
| `MODEL_VERSION` | `1.0.0` | Version to train (must be new) or to load |
| `DECISION_THRESHOLD` | `0.5` | Probability from which an order is eligible (0 to 1) |
| `RANDOM_STATE` | `42` | Seed for data generation, split and model |
| `LOG_LEVEL` | `INFO` | Minimum level of log messages shown: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Project structure

```
.
├── pyproject.toml                    # package definition (pip install -e .)
├── src/livraison_express/
│   ├── __main__.py                   # entry point: python -m livraison_express
│   ├── cli.py                        # commands train / predict / predict-batch
│   ├── config.py                     # settings from environment variables
│   ├── factory.py                    # picks the implementation for each abstraction
│   ├── api/
│   │   ├── app.py                    # FastAPI endpoints and error handling
│   │   ├── schemas.py                # Pydantic models = OpenAPI contract
│   │   ├── main.py                   # app instance for uvicorn
│   │   └── export_openapi.py         # writes docs/openapi.json
│   ├── abstractions/
│   │   ├── model_repository.py       # ModelRepository (ABC)
│   │   ├── order_data_source.py      # OrderDataSource (ABC)
│   │   └── explanation_generator.py  # ExplanationGenerator (ABC)
│   ├── core/
│   │   ├── domain.py                 # TrainedModel, Prediction, Factor
│   │   ├── features.py               # feature lists, categories, preprocessing
│   │   ├── data_quality.py           # validation and cleaning
│   │   ├── training.py               # pipeline, training, metrics
│   │   ├── predictor.py              # EligibilityPredictor
│   │   └── explanation.py            # contributions + TemplateExplanationGenerator
│   └── infrastructure/
│       └── dev/
│           ├── synthetic_orders.py       # SyntheticOrderSource
│           └── file_model_repository.py  # FileModelRepository
├── tests/
├── examples/                         # sample inputs
├── docs/
│   ├── adr/                          # architecture decision records
│   └── openapi.json                  # API contract (generated)
└── notebooks/                        # original experiment (reference only)
```

## Architecture

Business code (`core/`) depends only on abstractions. Entry points (CLI, API) and environment-specific classes (`infrastructure/`) are connected in one place, `factory.py` (dependency inversion, the "D" in SOLID).

```
  terminal ──> cli.py ───────┐
                             ├──> factory.py ──> core/ (predictor, training, explanation)
  HTTP ──────> api/ ─────────┘                      │
               (Pydantic, OpenAPI)                  v
                                       abstractions/ (ABC contracts)
                                                    ^
                                                    │ implemented by
                          infrastructure/dev/  +  core/explanation.py (template)
```

Decisions are recorded in `docs/adr/`:

- [ADR-0000](docs/adr/0000-model-artifact-storage.md): model artifacts in a local directory, one folder per version
- [ADR-0001](docs/adr/0001-order-data-source.md): training data source abstracted per environment
- [ADR-0002](docs/adr/0002-notebook-scope.md): which notebook code goes into the application
- [ADR-0003](docs/adr/0003-http-api.md): HTTP API, OpenAPI contract and explanations

## Status

- [x] Experimental notebook
- [x] Project structure
- [x] Notebook logic moved into `src/`
- [x] Model repository (abstraction + local file implementation)
- [x] Tests
- [x] Prediction API with OpenAPI contract
- [x] Template explanation (LLM-ready abstraction)
- [ ] LLM explanation generator
- [ ] Production data source and environment
- [ ] MLflow tracking
- [ ] CI/CD and deployment

## Limitations

- The dataset is synthetic; performance on real data may differ.
- The model is a decision aid and must not replace business rules.
- Explanations describe each feature's effect compared with an average order; they explain the model, not the real-world cause.
