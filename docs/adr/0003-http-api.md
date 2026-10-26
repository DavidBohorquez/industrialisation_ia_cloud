# ADR-0003: HTTP API with FastAPI, code-first OpenAPI and template explanations

- **Status:** Accepted
- **Date:** 2026-10-09

## Context

The final client needs predictions over HTTP, with a documented contract (OpenAPI), clear error messages, and a short readable explanation of each decision. A real LLM may write that explanation later, but must never be required for a prediction to succeed.

## Decisions

1. **FastAPI, code-first.** The Pydantic classes in `src/api/schemas.py` are the contract. FastAPI generates `/openapi.json` and Swagger UI (`/docs`) from them. `docs/openapi.json` is a committed copy; a test fails when it is outdated (`python -m src.api.export_openapi` regenerates it).
2. **Endpoints:** `POST /v1/predictions`, `POST /v1/predictions/batch` (max 1000 orders), `GET /v1/model`, `GET /health`. No training endpoint: training stays a CLI operation.
3. **Errors:** `422` with field, received value and rule (FastAPI/Pydantic default); `413` for oversized batches; `503` when no model is loaded; `500` with a reference only, details in server logs.
4. **Explanations:** `ExplanationGenerator` abstraction. `TemplateExplanationGenerator` lives in `src/core/` because it has no external dependency and must stay available in every environment as the rollback target if an LLM generator fails or is removed. A future `LlmExplanationGenerator` goes under `src/infrastructure/` and is selected in `src/factory.py`.
5. **Explanation facts:** the reasons come from exact logistic regression contributions (coefficient x transformed value), so the text can never contradict the model's decision.
6. **Pydantic stays in `src/api/`.** `src/core/` keeps plain dataclasses, so the business code does not depend on the web framework.

## Consequences

- Explanations are on by default for single predictions and off by default for batches (`?explain=`), to keep a future LLM's cost and latency under control.
- The API starts even without a model and reports `503` until one is available, so monitoring can detect it.
- `weekend` must be consistent with `day_of_week`; the API rejects contradictory orders instead of guessing.
