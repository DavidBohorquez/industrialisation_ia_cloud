# ADR-0001: Abstract the source of training orders

- **Status:** Accepted
- **Date:** 2026-10-07

## Context

The notebook generates synthetic orders. The course rules say the development environment uses generated data and has no access to production systems, while production uses real data (ERP, business software).
The training code must therefore run on different data sources depending on the environment.

## Options considered

| Option | Advantage | Drawback |
|---|---|---|
| A. Call the generator directly from training | Simplest | Training is tied to fake data; production needs a code change |
| B. `OrderDataSource` abstraction, one implementation per environment | Training code never changes between environments | One extra class |

## Decision

Option B. `OrderDataSource` lives in `src/abstractions/`, and `SyntheticOrderSource` in `src/infrastructure/dev/`.
`src/factory.py` selects the implementation from `APP_ENV`.

## Consequences

- Production needs a new implementation (e.g. reading the ERP database) and one line in `src/factory.py`.
- Until then, `APP_ENV` other than `dev` fails with a clear error instead of silently training on fake data.
- Tests can feed any data through an in-memory source.
