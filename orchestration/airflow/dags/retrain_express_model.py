"""Retrain the express delivery model when enough new labelled orders have arrived (ADR-0014).

    count_labelled_orders ──► enough_new_labels ──► train_model ──────────► record_labelled_count
    SQL count on the ERP      short-circuit: skip   DockerOperator: our      Airflow Variable,
    replica (erp_postgres)    the rest unless the   training image, run      written only after
                              count grew enough     on the host's Docker     a successful training

Why a schedule that looks at the data, and not CI (course slide 23): training is an execution
process, not a build step. A new model is needed when enough new labelled data has arrived, not
when the code changes; and the CI runners must never reach production data. So this DAG runs
every few minutes, measures the data, and trains only past a threshold.

Airflow orchestrates, our image computes (slide 24): this file never imports livraison_express.
Airflow's Python environment and the application's stay separate; the training runs in the same
image as `docker compose run --rm train`, with its own pinned dependencies.

Promotion is not part of this DAG: the API serves the MODEL_VERSION of its own configuration. A
version trained here is a candidate until someone reads its model card (metadata.json, MLflow)
and changes the API's MODEL_VERSION: a separate, manual step.
"""

import logging
import os
from datetime import timedelta
from urllib.parse import quote

import pendulum
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import BaseHook, Param, Variable, dag, task
from airflow.sdk.log import mask_secret
from docker.types import Mount

log = logging.getLogger("airflow.task")

# Airflow connection to the ERP read replica, defined by AIRFLOW_CONN_ERP_POSTGRES in
# docker-compose.yaml (read-only role ml_reader).
ERP_CONN_ID = "erp_postgres"

# Labels arrive late: the ERP simulator fills express_eligible once the outcome is known.
# Only labelled orders can train a model, so only they count.
LABELLED_ORDERS_SQL = "SELECT count(*) FROM orders WHERE express_eligible IS NOT NULL"

# Number of labelled orders at the last successful training.
LAST_COUNT_VARIABLE = "retrain_express_model_last_labelled_count"

# Read when the DAG file is parsed: the same .env reaches the dag-processor and the worker.
SCHEDULE = os.environ.get("RETRAIN_SCHEDULE", "*/10 * * * *")
TRAIN_IMAGE = os.environ.get("TRAIN_IMAGE", "livraison-express-train:local")
MIN_NEW_LABELLED_ORDERS = int(os.environ.get("MIN_NEW_LABELLED_ORDERS", "1000"))
MODEL_VERSION_PREFIX = os.environ.get("MODEL_VERSION_PREFIX", "2.0.0")
# Docker volumes of the environment's compose stack (default: docker-compose.test.yml, project
# "livraison-express-test"): the training writes the model where that API reads it, and the
# MLflow runs next to the earlier ones.
MODELS_VOLUME = os.environ.get("MODELS_VOLUME", "livraison-express-test_models")
MLRUNS_VOLUME = os.environ.get("MLRUNS_VOLUME", "livraison-express-test_mlruns")

# Unique per run, and a valid directory name for the model repository (artifacts/<version>/):
# <X.Y.Z>+<UTC date and time>, e.g. 2.0.0+20261120T101500 (SemVer build metadata: same recipe,
# newer data). run_after, not ts_nodash: Airflow 3 manual runs may have no logical date.
# Training refuses a version that already exists, hence no retries on train_model.
MODEL_VERSION = (
    "{{ params.model_version_prefix }}+{{ dag_run.run_after.strftime('%Y%m%dT%H%M%S') }}"
)


def erp_postgres_dsn() -> str:
    """POSTGRES_DSN of the training container, built from the erp_postgres connection.

    A template macro: it runs on the worker when train_model renders its templates, so the
    password is never written in this file, in XCom or in the serialized DAG. mask_secret hides
    the whole DSN (***) in the task logs and in the UI's "Rendered Template" view.
    """
    conn = BaseHook.get_connection(ERP_CONN_ID)
    dsn = (
        f"postgresql://{quote(conn.login or '', safe='')}:{quote(conn.password or '', safe='')}"
        f"@{conn.host}:{conn.port or 5432}/{conn.schema}"
    )
    mask_secret(dsn)
    return dsn


@dag(
    dag_id="retrain_express_model",
    description="Retrain the express eligibility model when enough new labelled orders arrived",
    doc_md=__doc__,
    schedule=SCHEDULE,
    start_date=pendulum.datetime(2026, 11, 1, tz="UTC"),
    # Each run measures the current data, so missed intervals need no replay...
    catchup=False,
    # ...and two trainings never run at the same time.
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=1),
    # No retries: the next scheduled run is the retry. A failed training leaves the Variable
    # unchanged, so the next run sees the same new labels and trains again, with a new version.
    default_args={"owner": "livraison-express", "retries": 0},
    params={
        "train_image": Param(TRAIN_IMAGE, type="string", description="Training image to run"),
        "min_new_labelled_orders": Param(
            MIN_NEW_LABELLED_ORDERS,
            type="integer",
            minimum=1,
            description="New labelled orders since the last training needed to train again",
        ),
        "model_version_prefix": Param(
            MODEL_VERSION_PREFIX,
            type="string",
            # X.Y.Z only: the version becomes a directory name, so no "/" or "..".
            pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$",
            description="Trained versions are named <prefix>+<UTC date and time of the run>",
        ),
    },
    user_defined_macros={"erp_postgres_dsn": erp_postgres_dsn},
    tags=["livraison-express", "training"],
)
def retrain_express_model():
    @task
    def count_labelled_orders() -> int:
        """Labelled orders in the ERP database (read-only role on the read replica)."""
        (count,) = PostgresHook(postgres_conn_id=ERP_CONN_ID).get_first(LABELLED_ORDERS_SQL)
        log.info("%d labelled orders in the ERP database.", count)
        return int(count)

    @task.short_circuit
    def enough_new_labels(labelled_count: int, **context) -> bool:
        """True: go on and train. False: skip train_model and record_labelled_count."""
        threshold = context["params"]["min_new_labelled_orders"]
        # No Variable yet (first run): every labelled order is new.
        last_count = int(Variable.get(LAST_COUNT_VARIABLE, default=0))
        if labelled_count < last_count:
            log.warning(
                "Labelled orders went down from %d to %d (ERP database reset?): counting from 0.",
                last_count,
                labelled_count,
            )
            last_count = 0
        new_labels = labelled_count - last_count
        log.info(
            "%d new labelled orders since the last training (%d then, %d now), threshold %d.",
            new_labels,
            last_count,
            labelled_count,
            threshold,
        )
        return new_labels >= threshold

    train_model = DockerOperator(
        task_id="train_model",
        image="{{ params.train_image }}",
        # The image's entrypoint is `python -m livraison_express`; this is its sub-command.
        command="train",
        # Settings of the application (src/livraison_express/config.py), as in docker compose.
        environment={
            "ORDER_SOURCE": "postgres",
            "POSTGRES_DSN": "{{ erp_postgres_dsn() }}",
            "MODEL_VERSION": MODEL_VERSION,
            "LOG_LEVEL": "INFO",
        },
        # The container joins the ERP network to reach host erp-postgres.
        network_mode="livraison-net",
        # The image paths of ARTIFACTS_DIR and MLFLOW_TRACKING_URI (Dockerfile, train stage).
        mounts=[
            Mount(source=MODELS_VOLUME, target="/app/artifacts", type="volume"),
            Mount(source=MLRUNS_VOLUME, target="/app/mlruns", type="volume"),
        ],
        # The worker is itself a container: the host's Docker engine cannot bind-mount a
        # temporary folder that only exists inside it.
        mount_tmp_dir=False,
        # The training logs are copied into the Airflow task log as they come: no container
        # needs to stay behind, even after a failure.
        auto_remove="force",
        # The last log line is not a useful result: nothing to push to XCom.
        do_xcom_push=False,
        execution_timeout=timedelta(minutes=30),
    )

    @task
    def record_labelled_count(labelled_count: int) -> None:
        """Runs only after a successful training: the next threshold starts from this count.

        The count was measured before the training, which may have read a few more labels:
        the next training can come slightly early, never late.
        """
        Variable.set(
            LAST_COUNT_VARIABLE,
            str(labelled_count),
            description="Labelled orders at the last successful training (retrain_express_model)",
        )
        log.info("Recorded %d labelled orders for the next threshold.", labelled_count)

    labelled_count = count_labelled_orders()
    enough_new_labels(labelled_count) >> train_model >> record_labelled_count(labelled_count)


retrain_express_model()
