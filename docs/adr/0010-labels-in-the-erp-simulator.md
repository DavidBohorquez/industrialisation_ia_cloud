# ADR-0010: Simulate the order outcome in the ERP simulator, revealed after a delay

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

Training needs examples whose answer is known: the features (X) and `express_eligible` (Y). The course's ERP simulator (`erp-simulator/`, TP4) writes orders into PostgreSQL and MongoDB without any `express_eligible` column. The professor confirmed it was forgotten and pointed to the generation heuristic of the course (notebook cell 8: a linear score, a sigmoid, then a random draw), which uses the application's vocabulary (`pluie`, `proche_banlieue`, `premium`, capacity 0-1) while the ERP uses its own (`rain`, `suburb`, `business`, capacity 5-50).

In reality an outcome is known only some time after the order. The simulator gives live batches simulated dates: one batch per few seconds, one simulated day per batch.

## Options considered

| Option | Advantage | Drawback |
|---|---|---|
| A. Compute Y in the simulator and store it in the orders table | The source system holds the outcome, as in real life; the application stays a pure reader | We maintain our copy of the professor's simulator |
| B. Compute Y in the application while reading | No change to the simulator | The application would contain the rule it is supposed to learn; changing the heuristic would silently rewrite past labels; translation and outcome simulation mixed in one adapter |
| C. An orchestrator task writes Y into a separate outcomes table that we own | Versioned labels, the usual enterprise pattern | A second writable database and a join across databases, for a course project |

## Decisions

1. **Option A.** `outcome.py` applies the heuristic with the same coefficients, sigmoid and Bernoulli draw, translated to ERP values: wind 0.20 (between rain 0.10 and storm 0.30), suburb 0.175 (midpoint of `proche_banlieue` 0.10 and `banlieue` 0.25), business +0.15 (like premium), `carrier_capacity / 50` (assumption: free capacity out of a maximum of 50). Unknown values and capacities outside 0-50 raise `ValueError`.
2. **Reproducible.** One seed per order (`random.Random("outcome:<order_id>")`): the same order gets the same outcome in every process; a seed built from `hash()` would change with `PYTHONHASHSEED`.
3. **A random draw, not a threshold.** A threshold would make Y an exact function of X: a model would reach about 100% and the metrics would mean nothing.
4. **Revealed after a simulated delay.** `orders.express_eligible` (`SMALLINT`, NULL while unknown; a field set to `null` in MongoDB) is filled for orders dated at least `LABEL_DELAY_DAYS` (default 2) simulated days before the latest simulated date, after the history and after each live batch. Live orders are therefore unlabelled for two batches: those are the orders a model would score.
5. **No outcome without its inputs.** `preparation_time_min` is NULL before July 2017: those orders keep a NULL outcome (imputing the input would fabricate the label). A NULL `weekend` (before July 2015) is taken from `day_of_week`, which is never NULL.
6. **Idempotent and restart-safe.** Updates only touch rows whose outcome is still NULL; MongoDB is updated without upsert (orders before 2023 do not exist there) and new orders are inserted only if absent (`$setOnInsert`; the handout's `ReplaceOne` erased known outcomes on restart); after a restart the simulated clock resumes the day after the latest order instead of going back to today.
7. **Testable orchestration.** The `Protocol` contracts move from `storage.py` to `contracts.py`, so `simulator.py` no longer imports the database drivers and its logic is tested with in-memory fakes.

## Consequences

- About 34% of ERP orders are eligible (79% with the notebook's data, whose distances are much shorter): the model must be judged with F1 and ROC AUC, not accuracy alone (always answering "no" gives 66% accuracy).
- About 31% of the default old history (2015 to mid-2017) has no outcome and is not used for training.
- The model learns an approximation of the course heuristic; the model card must say that the labels are simulated.
- Every difference with the handout is listed in `erp-simulator/README-erp-databases.md`.
- Because order dates are simulated, a scoring job must select new orders with a watermark (the last processed order sequence), not with the orchestrator's real-time intervals.
