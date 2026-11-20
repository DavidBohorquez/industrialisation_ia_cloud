import psycopg
import pytest

from livraison_express.config import Settings
from livraison_express.factory import build_model_repository, build_order_reader
from livraison_express.infrastructure.dev.file_model_repository import FileModelRepository
from livraison_express.infrastructure.dev.in_memory_order_repository import (
    InMemoryOrderRepository,
)
from livraison_express.infrastructure.postgres.postgres_order_reader import PostgresOrderReader


def settings(**values) -> Settings:
    return Settings(_env_file=None, **values)


def test_memory_source_reads_generated_labelled_orders():
    reader = build_order_reader(settings(order_source="memory", random_state=1))

    assert isinstance(reader, InMemoryOrderRepository)
    assert reader.count() > 0
    assert len(reader.get_training_data()) == reader.count()


def test_postgres_source_reads_the_configured_database():
    reader = build_order_reader(
        settings(order_source="postgres", postgres_dsn="postgresql://nobody@127.0.0.1:1/none")
    )

    assert isinstance(reader, PostgresOrderReader)
    # The DSN given in the settings is the one used: nothing listens on port 1.
    with pytest.raises(psycopg.OperationalError, match="127.0.0.1"):
        reader.count()


def test_models_are_stored_in_the_artifacts_directory(tmp_path):
    repository = build_model_repository(settings(order_source="memory", artifacts_dir=tmp_path))

    assert isinstance(repository, FileModelRepository)
    with pytest.raises(FileNotFoundError, match=str(tmp_path)):
        repository.load("1.0.0")
