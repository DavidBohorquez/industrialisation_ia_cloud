# ADR-0013: One setting per dependency instead of an environment profile

- **Status:** Accepted
- **Date:** 2026-11-20
- **Supersedes:** the environment-profile parts of [ADR-0001](0001-order-data-source.md) (`factory.py` selects the implementations from `APP_ENV`) and [ADR-0005](0005-align-with-correction.md) (one branch per environment in `factory.build_order_repository`)

## Context

`APP_ENV` chose every implementation from one environment name: `dev` meant generated orders and the file model store, and any other value failed. Session 4 adds a second order source, the ERP's PostgreSQL ([ADR-0012](0012-read-only-order-reader.md)). With a profile, `APP_ENV=prod` would have to mean "ERP orders, file models, ..." for every process of that environment. That does not hold:

- the training job (run by Airflow, ADR-0014) reads the ERP, while the API in the same environment reads no orders at all;
- a scoring job and a test run of the training job in the same environment can need different sources;
- a developer may train on a copy of the ERP while keeping the local file store.

Each such case adds a profile (`dev`, `dev-postgres`, `staging`...), and the name hides which implementations a process really uses. The [Twelve-Factor App](https://12factor.net/config) (factor III, config) describes this trap: settings are granular, independent environment variables, "never grouped together as environments".

## Decisions

1. **One setting per dependency, named after it.** `ORDER_SOURCE=memory|postgres` (default `memory`) chooses where orders come from; `POSTGRES_DSN` says how to reach the database. The model store stays the file store: it has one implementation, so it gets a setting when it gets a second one (e.g. `MODEL_STORE`). The same goes for a future LLM explanation generator.
2. **`APP_ENV` is removed.** Each function of `factory.py` reads only its own settings: `build_order_reader` reads `ORDER_SOURCE` and `POSTGRES_DSN`, `build_model_repository` reads `ARTIFACTS_DIR`.
3. **Validated at startup.** `ORDER_SOURCE` is a `Literal`: a typo stops the program. A `model_validator` in `config.py` stops it when `ORDER_SOURCE=postgres` has no `POSTGRES_DSN`, with a message naming both variables, before any work starts. An empty value counts as missing.
4. **The DSN is a secret.** It holds a password, so it is a pydantic `SecretStr`: shown as `**********` in `repr`, logs and validation errors, unwrapped once in `factory.py` to build the reader, never logged. It reaches a process through its environment (the Airflow connection, a `.env` file that git ignores), never through `.env.example` or an image. It names the read-only role (ADR-0009).
5. **Late import.** `factory.py` imports the PostgreSQL reader, and so `psycopg`, only when `ORDER_SOURCE=postgres`, as it does for MLflow.

Rejected:

- an `APP_ENV=prod` profile: see Context;
- choosing the source from the presence of `POSTGRES_DSN`: a DSN left in an environment would silently switch training to the ERP. `ORDER_SOURCE` makes the choice visible in the job's definition.

## Consequences

- Airflow runs the training image with `ORDER_SOURCE=postgres` and `POSTGRES_DSN`; the API needs neither.
- A fresh clone works with no configuration: orders are generated in memory.
- An `APP_ENV` left in an old `.env` is ignored (`extra="ignore"`).
- A new implementation of a dependency means one value in its `Literal`, one `case` in `factory.py`, and its own settings with their validation.
