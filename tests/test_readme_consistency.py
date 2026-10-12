import json
from pathlib import Path

import pytest

from be_power_forecast.readme import PLACEHOLDER, fmt, lookup, render

ROOT = Path(__file__).resolve().parents[1]


def test_readme_is_the_rendered_template():
    template = (ROOT / "docs" / "README.template.md").read_text()
    metrics = json.loads((ROOT / "results" / "metrics.json").read_text())
    readme = (ROOT / "README.md").read_text()
    assert PLACEHOLDER.findall(template), "the template has no placeholder"
    assert render(template, metrics) == readme, "README.md is stale: run make_report.py"
    assert "{{" not in readme and "}}" not in readme


def test_render_resolves_paths_and_formats():
    metrics = {"a": {"b c.": 1.23456, "list": [{"n": 7}]}, "p": 1e-20, "q": 0.0312}
    text = "x {{a/b c.}} {{a/b c.|.1f}} {{a/list/0/n|d}} {{p|p}} {{q|p}}"
    assert render(text, metrics) == "x 1.23 1.2 7 < 10⁻¹⁵ = 0.031"
    assert fmt("lear_ensemble", None) == "lear_ensemble"
    with pytest.raises(KeyError):
        lookup(metrics, "a/missing")
