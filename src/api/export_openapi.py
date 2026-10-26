import json
from pathlib import Path

from src.api.app import create_app
from src.config import PROJECT_ROOT
from src.core.explanation import TemplateExplanationGenerator

OPENAPI_FILE = PROJECT_ROOT / "docs" / "openapi.json"


def render_openapi() -> str:
    spec = create_app(None, TemplateExplanationGenerator()).openapi()
    return json.dumps(spec, indent=2, ensure_ascii=False) + "\n"


def main(output: Path = OPENAPI_FILE) -> None:
    output.write_text(render_openapi(), encoding="utf-8")
    print(f"Contrat OpenAPI écrit dans {output}.")


if __name__ == "__main__":
    main()
