from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

# Where the orders are read from (ADR-0013): generated in memory, or the ERP's PostgreSQL.
OrderSource = Literal["memory", "postgres"]


class Settings(BaseSettings):
    """Priority: environment variables, then the project's .env file, then these defaults.

    One setting per dependency (ADR-0013): each one chooses its own implementation in
    factory.py, instead of a single environment name choosing all of them.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    order_source: OrderSource = "memory"
    # SecretStr: shown as '**********' in repr, logs and validation errors (it holds a password).
    postgres_dsn: SecretStr | None = None
    artifacts_dir: Path = PROJECT_ROOT / "artifacts"
    model_version: str = "2.0.0"
    decision_threshold: float = Field(default=0.5, ge=0, le=1)
    random_state: int = 42
    log_level: LogLevel = "INFO"
    mlflow_tracking_uri: str = f"sqlite:///{PROJECT_ROOT / 'mlflow.db'}"
    mlflow_artifact_location: str = str(PROJECT_ROOT / "mlruns")

    @model_validator(mode="after")
    def _postgres_source_needs_a_dsn(self) -> Self:
        # Checked at startup: a missing DSN fails here, not after minutes of work in a job.
        if self.order_source == "postgres" and self.postgres_dsn is None:
            raise ValueError(
                "ORDER_SOURCE=postgres needs POSTGRES_DSN, e.g. "
                "postgresql://<user>:<password>@<host>:5432/<database>"
            )
        return self


def load_settings() -> Settings:
    return Settings()
