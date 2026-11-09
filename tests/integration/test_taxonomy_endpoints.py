"""Integration tests for SETUP-12 taxonomy API (T-S12-070)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_versions_returns_active(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.get("/api/v1/taxonomy/versions", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    # Bootstrap из seed/taxonomy/v1_0_0.yaml произошёл при init
    # taxonomy_registry в dependencies.py.
    assert body["active_version_id"] == "v1.0.0"
    assert len(body["versions"]) == 1
    v = body["versions"][0]
    assert v["version_id"] == "v1.0.0"
    assert v["is_active"] is True


def test_active_tree_returns_9_l0_classes(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.get("/api/v1/taxonomy/tree", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"]["version_id"] == "v1.0.0"
    # Seed имеет 9 L0 классов.
    assert len(body["roots"]) == 9
    assert body["total_classes"] == 9
    # L1/L2 пустые → 0 auto-created
    assert body["auto_created_count"] == 0
    # Каждый root имеет children=[]
    for root in body["roots"]:
        assert root["children"] == []
        assert root["node"]["level"] == 0
        assert root["node"]["parent_path"] == ""
        assert "display_name_ru" in root["node"]
        assert "doc_type_hint" in root["node"]


def test_specific_version_tree(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.get(
        "/api/v1/taxonomy/versions/v1.0.0/tree", headers=auth_headers
    )
    assert resp.status_code == 200


def test_nonexistent_version_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.get(
        "/api/v1/taxonomy/versions/v9.9.9/tree", headers=auth_headers
    )
    assert resp.status_code == 404


def test_requires_taxonomy_read_permission(client: TestClient) -> None:
    # Заголовки без X-Roles → 401 (anonymous).
    resp = client.get("/api/v1/taxonomy/tree")
    assert resp.status_code == 401


def test_seed_classes_have_doc_type_hint(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.get("/api/v1/taxonomy/tree", headers=auth_headers)
    body = resp.json()
    slugs_with_hint = {
        root["node"]["class_slug"]
        for root in body["roots"]
        if root["node"]["doc_type_hint"]
    }
    # Все 9 seed-классов имеют doc_type_hint.
    assert "task" in slugs_with_hint
    assert "schema" in slugs_with_hint
    assert "analytics" in slugs_with_hint
    assert len(slugs_with_hint) == 9
