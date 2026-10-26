# ADR-0003: HTTP API with FastAPI, code-first OpenAPI and template explanations

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

The final client needs predictions over HTTP, with a documented contract (OpenAPI), clear error messages, and a short readable explanation of each decision. A real LLM may write that explanation later, but must never be required for a prediction to succeed.

## Decisions

1. **FastAPI, code-first.** The Pydantic classes in `src/livraison_express/api/schemas.py` are the contract. FastAPI generates `/openapi.json` and Swagger UI (`/docs`) from them. `docs/openapi.json` is a committed copy; a test fails when it is outdated (`python -m livraison_express.api.export_openapi` regenerates it).
2. **Endpoints:** `POST /v1/predictions`, `POST /v1/predictions/batch` (max 1000 orders), `GET /v1/model`, `GET /health` (liveness), `GET /health/ready` (readiness). No training endpoint: training stays a CLI operation.
3. **Errors:** `422` with field, received value and rule (FastAPI/Pydantic default); `413` for oversized batches; `503` when no model is loaded; `500` with a reference only, details in server logs.
4. **Explanations:** `ExplanationGenerator` abstraction. `TemplateExplanationGenerator` lives in `src/livraison_express/core/` because it has no external dependency and must stay available in every environment as the rollback target if an LLM generator fails or is removed. A future `LlmExplanationGenerator` goes under `src/livraison_express/infrastructure/` and is selected in `src/livraison_express/factory.py`.
5. **Explanation facts:** the reasons come from exact logistic regression contributions (coefficient x transformed value), so the text can never contradict the model's decision.
6. **Pydantic stays in `src/livraison_express/api/`.** `src/livraison_express/core/` keeps plain dataclasses, so the business code does not depend on the web framework.

## Consequences

- Explanations are on by default for single predictions and off by default for batches (`?explain=`), to keep a future LLM's cost and latency under control.
- The API starts even without a model. `/health/ready` and the prediction endpoints report `503` until one is available, while `/health` stays `200`: an orchestrator stops routing traffic to the instance instead of restarting it, since a restart cannot create a missing model.
- `weekend` must be consistent with `day_of_week`; the API rejects contradictory orders instead of guessing.
