"""Integration tests for Classifier Library API (SETUP-13 / ADR-HTC-09)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fe_bot.api.dependencies import get_classifier_description_generator
from fe_bot.llm_gateway.exceptions import LLMUnavailableError

pytestmark = pytest.mark.integration


def test_tree_summary_bootstraps_from_seed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.get("/api/v1/classifier/tree", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    # seed/classifier/asu_v1.txt: 906 узлов + 1 синтетический корень.
    assert body["total_nodes"] == 907
    assert len(body["roots"]) == 1
    root = body["roots"][0]
    assert root["name"] == "АСУ"
    assert len(root["children_ids"]) == 12


def test_get_node_returns_children_and_rendered_prompt(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    tree_resp = client.get("/api/v1/classifier/tree", headers=auth_headers)
    root_id = tree_resp.json()["roots"][0]["node_id"]

    resp = client.get(f"/api/v1/classifier/tree/nodes/{root_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["children"]) == 12
    assert body["rendered_prompt"] is not None
    assert "АСУ" in body["rendered_prompt"]


def test_get_unknown_node_returns_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    resp = client.get("/api/v1/classifier/tree/nodes/ghost-node", headers=auth_headers)
    assert resp.status_code == 404


class TestCrudLifecycle:
    def test_create_update_delete_child(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        tree_resp = client.get("/api/v1/classifier/tree", headers=auth_headers)
        root_id = tree_resp.json()["roots"][0]["node_id"]

        create_resp = client.post(
            f"/api/v1/classifier/tree/nodes/{root_id}/children",
            headers=auth_headers,
            json={"name": "Интеграционный тест", "description": "smoke"},
        )
        assert create_resp.status_code == 201
        new_node = create_resp.json()
        assert new_node["name"] == "Интеграционный тест"
        assert new_node["is_leaf"] is True
        node_id = new_node["node_id"]

        patch_resp = client.patch(
            f"/api/v1/classifier/tree/nodes/{node_id}",
            headers=auth_headers,
            json={"prompt_override": "custom"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["prompt_override"] == "custom"

        clear_resp = client.patch(
            f"/api/v1/classifier/tree/nodes/{node_id}",
            headers=auth_headers,
            json={"clear_prompt_override": True},
        )
        assert clear_resp.json()["prompt_override"] is None

        delete_resp = client.delete(
            f"/api/v1/classifier/tree/nodes/{node_id}", headers=auth_headers
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted_count"] == 1

        get_resp = client.get(
            f"/api/v1/classifier/tree/nodes/{node_id}", headers=auth_headers
        )
        assert get_resp.status_code == 404

    def test_cannot_delete_root(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        tree_resp = client.get("/api/v1/classifier/tree", headers=auth_headers)
        root_id = tree_resp.json()["roots"][0]["node_id"]
        resp = client.delete(f"/api/v1/classifier/tree/nodes/{root_id}", headers=auth_headers)
        assert resp.status_code == 409


def test_auditor_cannot_write(client: TestClient) -> None:
    # AUDITOR имеет KB_CLASSIFIER_READ, но не KB_CLASSIFIER_WRITE.
    headers = {"X-User-Id": "u1", "X-Roles": "auditor"}
    tree_resp = client.get("/api/v1/classifier/tree", headers=headers)
    assert tree_resp.status_code == 200
    root_id = tree_resp.json()["roots"][0]["node_id"]

    resp = client.post(
        f"/api/v1/classifier/tree/nodes/{root_id}/children",
        headers=headers,
        json={"name": "X"},
    )
    assert resp.status_code == 403


class _FakeDescriptionGenerator:
    def __init__(self, description: str | None = None, *, raises: Exception | None = None):
        self._description = description
        self._raises = raises

    def generate(self, *, name: str, path: list[str]) -> str:
        if self._raises is not None:
            raise self._raises
        return self._description or f"Draft for {name}"


class TestGenerateDescription:
    def test_returns_llm_draft_without_saving(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        client.app.dependency_overrides[get_classifier_description_generator] = (
            lambda: _FakeDescriptionGenerator("Глубокая нейронная сеть.")
        )
        tree_resp = client.get("/api/v1/classifier/tree", headers=auth_headers)
        root_id = tree_resp.json()["roots"][0]["node_id"]

        resp = client.post(
            f"/api/v1/classifier/tree/nodes/{root_id}/generate-description",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {"description": "Глубокая нейронная сеть."}

        # Черновик НЕ сохранён автоматически — description узла не изменилось.
        node_resp = client.get(
            f"/api/v1/classifier/tree/nodes/{root_id}", headers=auth_headers
        )
        assert node_resp.json()["node"]["description"] == ""

    def test_llm_unavailable_returns_503(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        client.app.dependency_overrides[get_classifier_description_generator] = (
            lambda: _FakeDescriptionGenerator(raises=LLMUnavailableError("down"))
        )
        tree_resp = client.get("/api/v1/classifier/tree", headers=auth_headers)
        root_id = tree_resp.json()["roots"][0]["node_id"]

        resp = client.post(
            f"/api/v1/classifier/tree/nodes/{root_id}/generate-description",
            headers=auth_headers,
        )
        assert resp.status_code == 503

    def test_requires_write_permission(self, client: TestClient) -> None:
        headers = {"X-User-Id": "u1", "X-Roles": "auditor"}
        client.app.dependency_overrides[get_classifier_description_generator] = (
            lambda: _FakeDescriptionGenerator("x")
        )
        tree_resp = client.get("/api/v1/classifier/tree", headers=headers)
        root_id = tree_resp.json()["roots"][0]["node_id"]

        resp = client.post(
            f"/api/v1/classifier/tree/nodes/{root_id}/generate-description",
            headers=headers,
        )
        assert resp.status_code == 403
