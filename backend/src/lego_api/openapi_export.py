"""Vyexportuje OpenAPI schému do súboru pre frontend.

Spustenie: ``uv run python -m lego_api.openapi_export``
"""

import json
from pathlib import Path

DEFAULT_TARGET = Path(__file__).resolve().parents[3] / "frontend" / "openapi.json"


def main(target: Path = DEFAULT_TARGET) -> None:
    from lego_api.main import create_app

    schema = create_app().openapi()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Zapísané do {target} ({len(schema['paths'])} ciest)")


if __name__ == "__main__":
    main()
