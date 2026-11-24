"""Выгрузка контракта в docs/openapi.yaml: python export_openapi.py."""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.main import app  # noqa: E402

out = Path(__file__).resolve().parent.parent / "docs" / "openapi.yaml"
out.write_text(yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False), encoding="utf-8")
print(f"OK → {out}")