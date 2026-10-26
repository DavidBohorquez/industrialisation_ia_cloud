from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    """Priority: environment variables, then the project's .env file, then these defaults."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    environment: str = Field(default="dev", validation_alias="APP_ENV")
    artifacts_dir: Path = PROJECT_ROOT / "artifacts"
    model_version: str = "1.0.0"
    decision_threshold: float = Field(default=0.5, ge=0, le=1)
    random_state: int = 42
    log_level: LogLevel = "INFO"
    mlflow_tracking_uri: str = f"sqlite:///{PROJECT_ROOT / 'mlflow.db'}"
    mlflow_artifact_location: str = str(PROJECT_ROOT / "mlruns")


def load_settings() -> Settings:
    return Settings()
