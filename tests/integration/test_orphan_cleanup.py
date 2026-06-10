"""Integration: orphan file cleanup (T-S02-023)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fe_bot.setup.source_registry.service import InMemorySourceRegistry
from fe_bot.setup.upload.cleanup import OrphanCleanupService
from fe_bot.storage.artifact_service import InMemoryArtifactStorage

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Cleanup KB"},
        headers=headers,
    )
    return resp.json()["setup_job_id"]


def _admin_headers() -> dict[str, str]:
    return {"X-User-Id": "admin1", "X-Roles": "admin"}


class TestFindOrphans:
    """Unit-уровень — OrphanCleanupService.find_orphans."""

    def test_no_orphans_when_all_registered(self) -> None:
        storage = InMemoryArtifactStorage()
        registry = InMemorySourceRegistry()
        svc = OrphanCleanupService(storage=storage, registry=registry)
        assert svc.find_orphans() == []

    def test_finds_unregistered_path(self) -> None:
        storage = InMemoryArtifactStorage()
        registry = InMemorySourceRegistry()
        # Загружаем напрямую в storage без registration.
        storage.upload(
            setup_job_id="s1",
            source_document_id="src_orphan",
            filename="orphan.md",
            content_type="text/markdown",
            data=b"data",
        )
        svc = OrphanCleanupService(storage=storage, registry=registry)
        orphans = svc.find_orphans()
        assert len(orphans) == 1
        assert "orphan.md" in orphans[0]


class TestCleanupDryRun:
    def test_dry_run_does_not_delete(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import (
            get_artifact_storage,
            get_orphan_cleanup_service,
        )

        sid = _create_job(client, auth_headers)
        # Создаём orphan напрямую через storage.
        storage = app_with_clean_state.dependency_overrides[get_artifact_storage]()
        storage.upload(
            setup_job_id=sid,
            source_document_id="src_orphan",
            filename="orphan.md",
            content_type="text/markdown",
            data=b"orphan-content",
        )

        cleanup = app_with_clean_state.dependency_overrides[
            get_orphan_cleanup_service
        ]()
        result = cleanup.cleanup(dry_run=True, setup_job_ids=[sid])
        assert len(result.orphan_paths) == 1
        assert result.deleted_paths == []
        assert result.dry_run is True
        # Файл всё ещё в storage.
        assert len(storage.list_paths()) == 1


class TestCleanupRealRun:
    def test_real_cleanup_deletes_orphans(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import (
            get_artifact_storage,
            get_orphan_cleanup_service,
        )

        sid = _create_job(client, auth_headers)
        storage = app_with_clean_state.dependency_overrides[get_artifact_storage]()
        # Два orphan, один зарегистрированный
        storage.upload(
            setup_job_id=sid,
            source_document_id="src_orphan_1",
            filename="a.md",
            content_type="text/markdown",
            data=b"a",
        )
        storage.upload(
            setup_job_id=sid,
            source_document_id="src_orphan_2",
            filename="b.md",
            content_type="text/markdown",
            data=b"b",
        )

        # Через legitimate upload — создаём настоящий зарегистрированный.
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("real.md", b"r", "text/markdown")},
            headers=auth_headers,
        )

        cleanup = app_with_clean_state.dependency_overrides[
            get_orphan_cleanup_service
        ]()
        result = cleanup.cleanup(dry_run=False, setup_job_ids=[sid])
        # 2 orphans удалено, 1 legitimate остался.
        assert len(result.deleted_paths) == 2
        assert len(storage.list_paths()) == 1


class TestCleanupEndpoint:
    def test_admin_dry_run_returns_orphans(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_artifact_storage

        sid = _create_job(client, auth_headers)
        storage = app_with_clean_state.dependency_overrides[get_artifact_storage]()
        storage.upload(
            setup_job_id=sid,
            source_document_id="orphan_1",
            filename="x.md",
            content_type="text/markdown",
            data=b"x",
        )

        resp = client.post(
            f"/api/v1/admin/cleanup/orphans?setup_job_id={sid}",
            headers=_admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["dry_run"] is True
        assert body["orphans_found"] == 1
        assert body["deleted"] == 0
        assert "Dry run" in body["message"]

    def test_admin_real_run_deletes(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_artifact_storage

        sid = _create_job(client, auth_headers)
        storage = app_with_clean_state.dependency_overrides[get_artifact_storage]()
        storage.upload(
            setup_job_id=sid,
            source_document_id="orphan_1",
            filename="x.md",
            content_type="text/markdown",
            data=b"x",
        )

        resp = client.post(
            f"/api/v1/admin/cleanup/orphans?dry_run=false&setup_job_id={sid}",
            headers=_admin_headers(),
        )
        body = resp.json()
        assert body["dry_run"] is False
        assert body["deleted"] == 1

    def test_user_lacks_admin_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.post(
            "/api/v1/admin/cleanup/orphans",
            headers=auth_headers,  # роль user
        )
        assert resp.status_code == 403
