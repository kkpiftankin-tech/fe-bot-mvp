"""Integration: Artifact Storage Service (T-S01-016)."""

from __future__ import annotations

import pytest

from fe_bot.storage.artifact_service import (
    InMemoryArtifactStorage,
    ObjectNotFoundError,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def storage() -> InMemoryArtifactStorage:
    return InMemoryArtifactStorage()


class TestUploadDownload:
    def test_upload_returns_storage_path(self, storage: InMemoryArtifactStorage) -> None:
        path = storage.upload(
            setup_job_id="setup_1",
            source_document_id="src_1",
            filename="doc.md",
            content_type="text/markdown",
            data=b"# Hello",
        )
        assert path == "s3://source-documents/setup_1/src_1/doc.md"

    def test_download_returns_data(self, storage: InMemoryArtifactStorage) -> None:
        path = storage.upload(
            setup_job_id="setup_1",
            source_document_id="src_1",
            filename="doc.md",
            content_type="text/markdown",
            data=b"# Hello",
        )
        obj = storage.download(path)
        assert obj.data == b"# Hello"
        assert obj.content_type == "text/markdown"
        assert obj.size_bytes == 7
        assert len(obj.checksum) == 64  # SHA-256 hex

    def test_download_unknown_raises(self, storage: InMemoryArtifactStorage) -> None:
        with pytest.raises(ObjectNotFoundError):
            storage.download("s3://source-documents/nope/nope/nope.md")


class TestExists:
    def test_exists_returns_bool(self, storage: InMemoryArtifactStorage) -> None:
        path = storage.upload(
            setup_job_id="setup_1",
            source_document_id="src_1",
            filename="a.md",
            content_type="text/markdown",
            data=b"x",
        )
        assert storage.exists(path) is True
        assert storage.exists("s3://source-documents/unknown") is False


class TestDelete:
    def test_delete_removes_object(self, storage: InMemoryArtifactStorage) -> None:
        path = storage.upload(
            setup_job_id="setup_1",
            source_document_id="src_1",
            filename="a.md",
            content_type="text/markdown",
            data=b"x",
        )
        storage.delete(path)
        assert storage.exists(path) is False

    def test_delete_unknown_raises(self, storage: InMemoryArtifactStorage) -> None:
        with pytest.raises(ObjectNotFoundError):
            storage.delete("s3://source-documents/nope")


class TestPresignedURL:
    def test_presigned_url_for_existing(self, storage: InMemoryArtifactStorage) -> None:
        path = storage.upload(
            setup_job_id="setup_1",
            source_document_id="src_1",
            filename="a.md",
            content_type="text/markdown",
            data=b"x",
        )
        url = storage.presigned_url(path, expires_in=600)
        assert url.startswith("memory://artifacts/")
        assert "expires_in=600" in url

    def test_presigned_url_unknown_raises(self, storage: InMemoryArtifactStorage) -> None:
        with pytest.raises(ObjectNotFoundError):
            storage.presigned_url("s3://source-documents/nope")


class TestPathSafety:
    def test_path_traversal_blocked(self, storage: InMemoryArtifactStorage) -> None:
        # Имена с / превращаются в _, чтобы не выйти из bucket-prefix.
        path = storage.upload(
            setup_job_id="setup_1",
            source_document_id="src_1",
            filename="../../etc/passwd",
            content_type="text/plain",
            data=b"root:x:0:0",
        )
        assert "/etc/passwd" not in path
        assert path.endswith(".._.._etc_passwd")

    def test_backslash_in_filename(self, storage: InMemoryArtifactStorage) -> None:
        path = storage.upload(
            setup_job_id="setup_1",
            source_document_id="src_1",
            filename="windows\\path",
            content_type="text/plain",
            data=b"x",
        )
        assert "\\" not in path
