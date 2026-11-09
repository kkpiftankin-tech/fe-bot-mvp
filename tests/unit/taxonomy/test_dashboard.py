"""Smoke-test для Grafana dashboard JSON (SETUP-12 / T-S12-101)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


_DASHBOARD_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "observability"
    / "dashboards"
    / "taxonomy-health.json"
)


def test_dashboard_exists() -> None:
    assert _DASHBOARD_PATH.exists(), f"Missing dashboard at {_DASHBOARD_PATH}"


def test_dashboard_valid_json() -> None:
    payload = json.loads(_DASHBOARD_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert payload["title"]
    assert payload["uid"] == "fe-bot-taxonomy-health"
    assert "taxonomy" in payload["tags"]


def test_dashboard_metrics_match_implementation() -> None:
    """Все метрики из TaxonomyMetrics присутствуют в dashboard'е."""
    text = _DASHBOARD_PATH.read_text(encoding="utf-8")
    expected = [
        "taxonomy_classification_total",
        "taxonomy_new_class_total",
        "taxonomy_force_merge_total",
        "taxonomy_llm_unknown_total",
        "taxonomy_classification_latency_seconds_bucket",
        "taxonomy_slots_used",
    ]
    missing = [m for m in expected if m not in text]
    assert not missing, f"Dashboard missing metrics: {missing}"


def test_dashboard_panels_have_targets() -> None:
    payload = json.loads(_DASHBOARD_PATH.read_text(encoding="utf-8"))
    panels = payload.get("panels", [])
    chart_panels = [
        p for p in panels if p.get("type") in {"timeseries", "stat"}
    ]
    assert len(chart_panels) >= 5
    for p in chart_panels:
        targets = p.get("targets", [])
        assert targets, f"Panel {p.get('id')} has no targets"
        assert all(t.get("expr") for t in targets), f"Panel {p.get('id')}: empty expr"
