# ADR-0011: Canonical order vocabulary and one adapter per source

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

The application's category values come from the notebook (cell 8): `weather` normal | pluie | neige | orage, `delivery_zone` centre | proche_banlieue | banlieue | rurale, `customer_type` standard | premium. They are the HTTP contract (enums in `docs/openapi.json`) and the categories the model's one-hot encoder learned.

The first real source, the ERP read from PostgreSQL (ADR-0009), describes the same orders with other values: `weather` clear | rain | snow | wind, `delivery_zone` centre | suburb | rural, `customer_type` individual | business, `carrier_capacity` as free capacity out of 50 instead of a 0-1 share, and `NULL`s in old rows (`weekend` before July 2015, `preparation_time_min` before July 2017). Its outcome is computed by the simulator with the course heuristic (ADR-0010). Other sources may follow (another ERP, CSV imports, a partner API).

An adapter between a source and the application can rename a value (rain → pluie), convert a unit (free capacity → share) and derive a field from another (weekend from day_of_week). It cannot:

- **invent detail its source does not have:** the ERP's single `suburb` cannot be split into `proche_banlieue` and `banlieue`; any split rule would be a guess, and the model would learn from it;
- **fix a meaning that differs:** individual / business is a customer kind (B2C / B2B); standard / premium is a service tier. Mapping one onto the other gives the model a feature that does not mean what it was trained on;
- **turn one concept into another:** wind is not a storm; mapping `wind` to `orage` would teach the model storm effects from windy days.

This gives a granularity rule: **a canonical model cannot hold more detail than its poorest source provides.** A canonical value may still exist when a source never produces it (the ERP has no storm, so ERP orders never carry `orage`), as long as no source value has to be split to reach it.

Options compared:

| | A. ERP vocabulary everywhere | B. Ours unchanged, approximate mapping | C. Ours adjusted minimally, one adapter per source |
|---|---|---|---|
| Change in the application | every value renamed (core, API, model) | none | `vent` added, `proche_banlieue` merged into `banlieue`, customer type replaced |
| ERP mapping | identity | suburb → banlieue or proche_banlieue (arbitrary), wind → orage (wrong meaning), individual / business → standard / premium (different concept) | renames only, one value to one value |
| Next source | must speak the ERP's language, or everything changes again | same approximations | one new adapter |
| Main risk | the public contract follows a vendor's schema | features that are silently wrong | breaking API change now |

## Decisions

1. **The application keeps its own canonical vocabulary** (option C), defined once in `src/livraison_express/core/features.py` (`Literal` types and `CATEGORY_VALUES`). The core, the model and the API only know these values. Pydantic reads the same `Literal` types, so the OpenAPI enums follow automatically.
2. **The vocabulary is adjusted so that every known source maps into it one to one:**

   | Field | Before | Now | Why |
   |---|---|---|---|
   | `weather` | normal, pluie, neige, orage | normal, pluie, neige, orage, **vent** | strong wind without a storm is its own case |
   | `delivery_zone` | centre, proche_banlieue, banlieue, rurale | centre, **banlieue**, rurale | the ERP only knows "suburb": the two suburbs cannot be told apart |
   | `customer_type` | standard, premium | **particulier, professionnel** | the ERP gives B2C / B2B, not a service tier |
   | `carrier_capacity` | free share, 0-1 | unchanged | the adapter converts |

3. **One adapter per source, in `infrastructure/`** (an anti-corruption layer), next to the code that reads that source. It turns a source row into a canonical order dict. The ERP adapter (written with the PostgreSQL reader, ADR-0012) maps:

   | Field | ERP | Canonical |
   |---|---|---|
   | `weather` | clear / rain / snow / wind | normal / pluie / neige / vent |
   | `delivery_zone` | centre / suburb / rural | centre / banlieue / rurale |
   | `customer_type` | individual / business | particulier / professionnel |
   | `carrier_capacity` | free capacity, 0-50 | value / 50 (assumption: free capacity out of a maximum of 50) |
   | `weekend` | `NULL` | derived from `day_of_week` (1 for 5 and 6) |
   | `preparation_time_min` | `NULL` | stays `None`: no value is invented |

   No ERP value maps to `orage`.
4. **Adapters are application code, not orchestration.** Airflow (ADR-0014) schedules and starts jobs; it does not translate data. In `infrastructure/` the mapping is tested with pytest, versioned with the vocabulary it targets, and the same for every job that reads the source. In a DAG, a vocabulary change would need two coordinated changes in two deployed units, and the CLI could not reuse it.
5. **Unknown source values are rejected, never guessed.** An adapter maps with an explicit table. A value missing from the table is not passed on with a default or a "closest" value: the order is rejected and logged with the field, the value and the order id. A new source value is added to the table on purpose, with its canonical meaning, or with a vocabulary change if none fits.
6. **The core checks again** (course: do not trust data quality, validate in the ETL and in the application). `validate_dataset` stops a training run and `MLPredict` rejects CLI inputs when a value is outside the vocabulary; the API answers `422` (Pydantic `Literal`). Without this check the encoder (`handle_unknown="ignore"`) would score the order as if the field were missing, without any error.
7. **Versions (SemVer, ADR-0006).** Removing and renaming enum values breaks the HTTP contract: `API_VERSION` becomes 2.0.0 and the next application release is a major one. The routes keep their `/v1` prefix because no external client exists yet; a public API would publish `/v2` next to `/v1` for a deprecation period. The API does not translate old values either: `standard` / `premium` have no canonical equivalent. The default `MODEL_VERSION` becomes 2.0.0, so that the new code never loads a model trained on the old vocabulary (1.0.0), whose encoder would ignore `vent`, `particulier` and `professionnel`.

## Consequences

- API clients must change their requests: the CHANGELOG gives the old → new table. Old values now get a `422` that lists the allowed ones.
- The notebook is not changed (ADR-0002): it still documents the original experiment with the old vocabulary, and its models cannot be loaded by the application.
- The dev generator (`infrastructure/dev/order_generator.py`) keeps the notebook's formula and numeric distributions and uses the canonical values with the ERP simulator's penalties (vent 0.20, banlieue 0.175 = mean of the old 0.10 and 0.25, professionnel +0.15), so dev data follows the same rules as ERP data. Measured on 6000 orders: the share of eligible orders is unchanged (78.8 %); the mean ROC AUC over 8 seeds goes from 0.826 to 0.817, within the seed-to-seed spread (±0.03).
- Every model must be retrained: 2.0.0 on dev data, then on ERP data. The vocabularies now match, the distributions do not: about 34 % of ERP orders are eligible against 79 % in dev (ERP distances are uniform between 1 and 40 km), so a dev model is no reference for ERP performance.
- Detail is lost: the model can no longer tell near from far suburbs (`distance_km` still carries most of that), and the premium tier is gone. Bringing it back needs a source that provides it, as a new feature (e.g. `service_tier`), not by reusing `customer_type`.
- A new source is one adapter and its mapping table, with tests. Renaming or removing a canonical value is a breaking change (major API version, new model); adding one is backward compatible for clients but needs a new model.
- Rejected orders are only logged. Failing a run when too many are rejected (e.g. a new ERP value) is left to the orchestration and monitoring work.
