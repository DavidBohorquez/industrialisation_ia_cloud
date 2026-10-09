import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    environment: str
    artifacts_dir: Path
    model_version: str
    decision_threshold: float
    random_state: int


def load_settings() -> Settings:
    return Settings(
        environment=os.getenv("APP_ENV", "dev"),
        artifacts_dir=Path(os.getenv("ARTIFACTS_DIR", PROJECT_ROOT / "artifacts")),
        model_version=os.getenv("MODEL_VERSION", "1.0.0"),
        decision_threshold=float(os.getenv("DECISION_THRESHOLD", "0.5")),
        random_state=int(os.getenv("RANDOM_STATE", "42")),
    )
