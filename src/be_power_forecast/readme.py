"""Render a Markdown template whose numbers are placeholders read from ``metrics.json``.

A placeholder is ``{{path|format}}``: ``path`` walks the metrics with ``/`` between keys
(keys may contain spaces and dots; list items by position), ``format`` is a Python format
spec (default ``.2f``) or ``p`` for a p-value. Keys cannot contain ``/``, ``|`` or braces.
Every placeholder must resolve, so no number is typed by hand.
"""

from __future__ import annotations

import re

PLACEHOLDER = re.compile(r"\{\{([^{}|]+)(?:\|([^{}]*))?\}\}")


def lookup(metrics: dict, path: str):
    value = metrics
    for key in path.strip().split("/"):
        if isinstance(value, list) and key.isdigit() and int(key) < len(value):
            value = value[int(key)]
        elif isinstance(value, dict) and key in value:
            value = value[key]
        else:
            raise KeyError(f"metrics.json has no '{path}'")
    return value


def fmt(value, spec: str | None) -> str:
    if spec == "p":  # p-value with its relation sign: "< 10⁻¹⁵" (numerically zero) or "= 0.031"
        return "< 10⁻¹⁵" if value < 1e-15 else f"= {value:.2g}"
    if isinstance(value, str):
        return value
    return format(value, spec if spec is not None else ".2f")


def render(template: str, metrics: dict) -> str:
    """Replace every placeholder of ``template`` by its formatted value."""
    return PLACEHOLDER.sub(lambda m: fmt(lookup(metrics, m.group(1)), m.group(2)), template)
