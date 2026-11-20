# ADR-0009: Read orders from PostgreSQL through a read-only replica

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

TP4 replaces the synthetic orders with the ERP's. Two databases hold them (course slides 12 and 13):

```
ERP <── two-way, real time ──> PostgreSQL (production) ── ETL, one-way, real time ──> MongoDB (analytics)
```

| | PostgreSQL | MongoDB |
|---|---|---|
| Role | first database of the software (2015), production; also used by another business-critical application | analytics copy built in 2023 because data analysts kept breaking production |
| History | 2015 -> today | 2023 -> today only: the older history was never copied |
| Schema | changed in 2017 and 2023, not updated since 2023; `weekend` is NULL before 2015-07-01, `preparation_time_min` before 2017-07-01 | schemaless; no NULLs, `order_date` stored as a datetime |
| Owner | nobody: the administrator resigned | an apprentice whose contract ends soon |

Measured with the simulator (`erp-simulator/`): PostgreSQL gets 10,000 + 1,000 historical orders, MongoDB the 1,000 from 2023, and both the same live orders. Both use the ERP's vocabulary (`rain`, `suburb`, `business`...), not the application's.

The course rules: an analytics database is for data teams only (slide 19); data teams read a replica of production, where nothing they do affects production (slide 20); data quality is not trusted and is validated in the ETL and in the application (slide 17); training is a run, not a build step (slide 23).

The choice has two questions. **Engine**: which data and which schema we learn from. **Role**: which server and which account we connect with, so what our code can break. The engine decides the quality of the model; the role decides whether a bug or a heavy query in a training job can stop the ERP and the other critical application. The role weighs more: a weaker dataset costs model quality, a write or a full scan on the production primary costs the business.

## Options considered

| Option | For | Against |
|---|---|---|
| A. PostgreSQL primary | Full history, source of truth, nothing to add | Training scans compete with the ERP and another critical application; any mistake runs on production; contradicts slide 20 |
| B. PostgreSQL streaming replica, read-only role `ml_reader` | Same data as A, normally less than a second behind; writes impossible twice (the role and the server); heavy queries load the replica only (slide 20) | One more server; asynchronous, may lag; inherits undocumented schema changes; needs the approval of whoever owns the primary (nobody today) |
| C. MongoDB analytics database | Built for data teams (slide 19) and already outside production; no NULLs | Only 2023 onwards; no schema, so no contract on fields or types; fed by an ETL whose owner is leaving, so its errors add to PostgreSQL's |

The case for C is fair: it is the database the company built for us, isolated by design, with cleaner data. With a documented ETL that someone owns, and if four years of history were enough, C would be a sound choice. Today its history is the deciding gap: orders before July 2017 have no label (ADR-0010), so with the simulator's default volumes PostgreSQL gives about 7,900 labelled orders over nine years, MongoDB 1,000 over four.

## Decisions

1. **Engine: PostgreSQL,** for the complete history and a typed schema. Its NULL columns are a known gap that tests can cover.
2. **Role: never the production primary.** The application reads with `ml_reader` (`SELECT` only, `default_transaction_read_only = on`; created by `erp-simulator/docker/erp/postgres-init.sql`) from a streaming read replica. Reading MongoDB would be better than reading the primary.
3. **The replica in the simulator stack.** `erp-simulator/docker-compose.replica.yml` overrides `docker-compose.erp.yml`, whose services stay unchanged:
   - `docker/erp/02-replication.sh` gives the primary a `replicator` role (`REPLICATION LOGIN`, no table rights) and a `host replication replicator` line in `pg_hba.conf`: the image's `host all all all` line does not cover replication connections;
   - `postgres-replica` clones the primary once with `pg_basebackup -R -X stream` (`docker/erp/replica-entrypoint.sh`), then runs as a hot standby: any write fails with `cannot execute INSERT in a read-only transaction`;
   - on the shared network `livraison-net`, only the replica answers to `erp-postgres`; the primary is kept off that network. The application uses `POSTGRES_DSN=postgresql://ml_reader:...@erp-postgres:5432/livraison_express` (ADR-0013).
4. **Fallback: if a replica or read-only access to PostgreSQL cannot be obtained, switch to MongoDB** (option C) and accept the 2023 history. Only a new reader adapter is needed (ADR-0011, ADR-0012).

Labels are computed by the ERP simulator (ADR-0010), the ERP vocabulary is translated by a source adapter (ADR-0011), and the application only reads (`OrderReader`, ADR-0012).

## Consequences

| Risk | Mitigation |
|---|---|
| The primary is shared with a business-critical application | Its DSN is never given to the application or the training job, and it is not on `livraison-net` |
| Nobody has owned PostgreSQL since 2023 | Organisational, not technical: before production, our team must get approval for the replica and the roles, and an owner for them |
| Undocumented schema changes (2017, 2023, future ones) reach the replica unchanged | The adapter validates columns, types and values and fails loudly on unknown ones (ADR-0011, slide 17) |
| NULL history | `weekend` is derived from `day_of_week`; orders without `preparation_time_min` have no label and are not used for training (ADR-0010, ADR-0011) |
| The asynchronous replica can lag the primary | Accepted: availability over consistency (CAP, slides 27-29); a model trained without the last seconds of orders is the same model. The healthcheck requires "in recovery and answering", not "streaming", so reads go on while the primary is down |
| No replication slot | A replica stopped longer than the primary keeps its WAL must be cloned again (delete its volume); in exchange, a forgotten replica can never fill the critical primary's disk |
| WAL replay can cancel long queries on the standby (`max_standby_streaming_delay`, 30 s) | Training reads one table in seconds; `hot_standby_feedback` stays off because it bloats the primary |

- Verified on the stack: after the simulator finishes, the replica has the same `count(*)` as the primary, `pg_is_in_recovery()` is true, an `INSERT` fails, and a stopped then restarted replica catches up with the orders written meanwhile.
- The init scripts run only on an empty primary volume. For a volume created before the override, its header gives the command that creates the role without losing data.
- The passwords (`replicator`, `ml_reader`) are for the local stack only; a real deployment injects them as secrets and restricts the `pg_hba.conf` line to the replica's address.
- The override needs Docker Compose 2.24.4 or later (`!override` tag).
