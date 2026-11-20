# ADR-0012: Read the ERP through an OrderReader that cannot write

- **Status:** Accepted
- **Date:** 2026-11-20
- **Amends:** decision 2 of [ADR-0005](0005-align-with-correction.md) (`OrderRepository` split into `OrderReader` and `OrderWriter`)

## Context

Session 4 asks for an `OrderRepository` implementation for the chosen database, PostgreSQL ([ADR-0009](0009-read-orders-from-postgres-replica.md)). Slide 10 shows one interface with `save`, `get` and `get_all`, implemented by `PostgresOrderRepository` and `MongoOrderRepository`.

That database belongs to the company's ERP: orders are its records, and our application only consumes them (training today, scoring jobs later). It must never write there; a bug that does would corrupt production data. Our `OrderRepository` (ADR-0005) bundles `save` with the reads, so a PostgreSQL implementation had two choices, both bad:

- implement `save`: a write path into production exists, one wrong call away;
- raise `NotImplementedError` in `save`: this breaks Liskov substitution. Code holding an `OrderRepository` may call `save`, the type promises it works, and the failure only shows at run time.

The training job never calls `save`: it only needs `get_training_data`.

## Decisions

1. **Interface segregation (the "I" in SOLID).** `abstractions/order_repository.py` defines two ABCs: `OrderReader` (`get`, `get_all`, `count`, `get_training_data`) and `OrderWriter` (`save`). `OrderRepository(OrderReader, OrderWriter)` keeps the course's name for a read and write store the application owns: `InMemoryOrderRepository` (dev and tests).
2. **Code depends on what it uses.** `run_training` takes an `OrderReader`; `factory.build_order_reader` returns one. Anything that only reads orders does the same.
3. **`PostgresOrderReader` implements `OrderReader` only.** It has no `save` method: writing is impossible by construction, not refused at run time. A call to `save` is flagged by a type checker and fails with `AttributeError`; `isinstance(reader, OrderWriter)` is false.
   Rejected: `PostgresOrderRepository` with a `save` that raises (breaks Liskov, see Context) or that writes (a write path into production).
4. **Three layers of protection.** Each one alone stops a write; together, a mistake in one of them (a DSN with a writable role, a raw SQL statement slipped into the reader) is still stopped.

   ```
   training job ──► PostgresOrderReader ──► psycopg connection ──► ml_reader role ──► read replica
                    1. no save() method     2. read_only = True    3. SELECT only,    4. hot standby:
                       (by construction)       BEGIN READ ONLY        default read     rejects every
                                               on each transaction    only (ADR-0009)  write
   ```

5. **Adapter rules.** Every row goes through `erp_order_mapper.erp_row_to_order` (ERP vocabulary to ours, [ADR-0011](0011-canonical-vocabulary-and-source-adapters.md)). The reader selects an explicit column list, sorts by `order_id COLLATE "C"` (byte order: the same as Python's `sorted()` and the same on every server, whatever its locale), reads labelled orders with `WHERE express_eligible IS NOT NULL`, and opens one short connection per call. A row the mapper rejects is skipped; one warning per read lists each distinct problem (field and value) with its count and a few order ids. It never reaches training, and `validate_dataset` checks the categories again (ADR-0011).
6. **One contract, tested on every implementation.** The reader contract now says `get_all` and `get_training_data` are sorted by `order_id`: the same orders give the same training set, so the same model, whatever the store (`InMemoryOrderRepository` sorts too). `tests/test_order_repository.py` runs the reader contract on `READERS` (in memory and PostgreSQL) and the writer contract on `REPOSITORIES` (in memory). Each store is seeded in its own format: canonical dicts in memory, ERP rows through an admin connection in PostgreSQL.

Deviation from slide 10: the slide's interface fits a store the application owns. For a source another system owns, a write method is a liability, so the read side is split out. The course's names stay recognisable: its `OrderRepository` is ours (read and write), and its `PostgresOrderRepository` becomes `PostgresOrderReader`.

## Consequences

- Storing orders ourselves (for example the API's requests, left open by ADR-0005) needs an `OrderWriter` on a store the application owns, never on the ERP.
- `count()` counts every row, `get_all()` only the rows that could be translated: the difference is the number of skipped rows, a data quality signal.
- `psycopg[binary]` is a core dependency (training and future scoring jobs read orders). `factory.py` imports the reader only when `ORDER_SOURCE=postgres` ([ADR-0013](0013-per-dependency-settings.md)), and `tests/test_dependency_boundary.py` fails if the API or the CLI imports `psycopg`. The serving image carries the driver without loading it.
- Tests that need PostgreSQL carry the `postgres` marker and skip unless `TEST_POSTGRES_DSN` is set. Each test creates its own schema and drops it afterwards, so it never touches `public.orders`. The CI job `postgres tests` runs them against a `postgres:17-alpine` service container.
