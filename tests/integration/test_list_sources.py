"""Integration: GET /sources (T-S03-012)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Sources KB"},
        headers=headers,
    )
    return resp.json()["setup_job_id"]


def _upload(
    client: TestClient,
    sid: str,
    headers: dict[str, str],
    filename: str = "a.md",
    content: bytes = b"x",
) -> str:
    resp = client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": (filename, content, "text/markdown")},
        headers=headers,
    )
    return resp.json()["uploaded"][0]["source_document_id"]


class TestListSourcesHappyPath:
    def test_empty_job_returns_empty_list(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}/sources", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["setup_job_id"] == sid
        assert body["items"] == []
        assert body["pagination"]["total"] == 0

    def test_lists_uploaded_documents(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers, filename="a.md", content=b"AAA")
        _upload(client, sid, auth_headers, filename="b.md", content=b"BBB")
        resp = client.get(f"/api/v1/setup/{sid}/sources", headers=auth_headers)
        body = resp.json()
        assert body["pagination"]["total"] == 2
        filenames = sorted(i["filename"] for i in body["items"])
        assert filenames == ["a.md", "b.md"]

    def test_list_item_has_checksum_short(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        body = client.get(f"/api/v1/setup/{sid}/sources", headers=auth_headers).json()
        assert len(body["items"][0]["checksum_short"]) == 12

    def test_list_item_has_counters(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        item = client.get(f"/api/v1/setup/{sid}/sources", headers=auth_headers).json()["items"][0]
        # Без downstream artifacts — все counters = 0.
        assert item["parsed_sections_count"] == 0
        assert item["rag_cards_count"] == 0
        assert item["chunks_count"] == 0


class TestListSourcesFilters:
    def test_filter_by_status(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """T-S03-019: после upload status=registered (не uploaded)."""
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}/sources?status=registered", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 1

    def test_filter_by_status_excludes_other(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}/sources?status=parsed", headers=auth_headers)
        assert resp.json()["pagination"]["total"] == 0

    def test_filter_by_owner(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}/sources?owner=u1", headers=auth_headers)
        assert resp.json()["pagination"]["total"] == 1
        resp = client.get(f"/api/v1/setup/{sid}/sources?owner=other_user", headers=auth_headers)
        assert resp.json()["pagination"]["total"] == 0

    def test_include_removed_default_hidden(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        client.delete(f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers)
        # Без include_removed.
        body = client.get(f"/api/v1/setup/{sid}/sources", headers=auth_headers).json()
        assert body["pagination"]["total"] == 0
        # С include_removed.
        body = client.get(
            f"/api/v1/setup/{sid}/sources?include_removed=true",
            headers=auth_headers,
        ).json()
        assert body["pagination"]["total"] == 1


class TestListSourcesPaginationAndSort:
    def test_pagination_default(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        for i in range(5):
            _upload(client, sid, auth_headers, filename=f"f{i}.md", content=f"c{i}".encode())
        body = client.get(
            f"/api/v1/setup/{sid}/sources?page=1&page_size=2", headers=auth_headers
        ).json()
        assert len(body["items"]) == 2
        assert body["pagination"]["total"] == 5

    def test_pagination_second_page(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        for i in range(5):
            _upload(client, sid, auth_headers, filename=f"f{i}.md", content=f"c{i}".encode())
        body = client.get(
            f"/api/v1/setup/{sid}/sources?page=2&page_size=3", headers=auth_headers
        ).json()
        assert len(body["items"]) == 2  # 5 total, page 2 of 3 = items 4-5

    def test_sort_by_filename_asc(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers, filename="z.md", content=b"z")
        _upload(client, sid, auth_headers, filename="a.md", content=b"a")
        body = client.get(
            f"/api/v1/setup/{sid}/sources?sort=filename:asc", headers=auth_headers
        ).json()
        assert [i["filename"] for i in body["items"]] == ["a.md", "z.md"]

    def test_sort_invalid_field_400(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}/sources?sort=hacker_field", headers=auth_headers)
        assert resp.status_code == 400


class TestListSourcesAccessControl:
    def test_unknown_job_404(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = client.get("/api/v1/setup/unknown_xxx/sources", headers=auth_headers)
        assert resp.status_code == 404

    def test_other_user_403(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/sources",
            headers={"X-User-Id": "other_user", "X-Roles": "user"},
        )
        assert resp.status_code == 403
