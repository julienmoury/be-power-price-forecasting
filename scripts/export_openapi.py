"""Write the OpenAPI schema of the forecast service to docs/openapi.json.

The schema is the contract with the projects that consume the forecasts;
tests/test_api.py fails when the service and this file disagree.
Usage: python scripts/export_openapi.py
"""

from __future__ import annotations

import json

from be_power_forecast.api.app import app
from be_power_forecast.config import REPO_ROOT

PATH = REPO_ROOT / "docs" / "openapi.json"

if __name__ == "__main__":
    PATH.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"wrote {PATH}")
