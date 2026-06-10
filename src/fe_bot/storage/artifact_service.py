"""Artifact Storage Service (SVC-38).

В S2 используется in-memory реализация. MinIO-клиент подменяется в INF-003
(T-S01-INF-003) без изменения зависимых сервисов (Protocol-интерфейс).

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-46.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


class StorageError(Exception):
    """Базовый класс ошибок хранилища."""


class ObjectNotFoundError(StorageError):
    def __init__(self, storage_path: str) -> None:
        self.storage_path = storage_path
        super().__init__(f"Object not found: {storage_path}")


class StorageUnavailableError(StorageError):
    """Аналог OBJECT_STORAGE_UNAVAILABLE из §18.2 SETUP-01."""


@dataclass(frozen=True, slots=True)
class StoredObject:
    """Содержимое объекта + базовые метаданные."""

    data: bytes
    content_type: str
    size_bytes: int
    checksum: str  # SHA-256 без префикса


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ArtifactStorage(Protocol):
    """Контракт хранилища артефактов."""

    def upload(
        self,
        *,
        setup_job_id: str,
        source_document_id: str,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> str:
        """Сохраняет объект и возвращает storage_path."""
        ...

    def download(self, storage_path: str) -> StoredObject: ...

    def exists(self, storage_path: str) -> bool: ...

    def delete(self, storage_path: str) -> None: ...

    def presigned_url(self, storage_path: str, expires_in: int = 3600) -> str: ...

    def list_paths(self, prefix: str | None = None) -> list[str]:
        """T-S02-023: возвращает все storage_paths (опционально с фильтром).

        В Qdrant/MinIO realtime listing дорогой; в продакшене этот метод
        используется только cleanup'ом (вне горячего пути).
        """
        ...


class InMemoryArtifactStorage:
    """In-memory реализация для S2/MVP."""

    BUCKET = "source-documents"

    def __init__(self, base_url: str = "memory://artifacts") -> None:
        self._store: dict[str, StoredObject] = {}
        self._base_url = base_url.rstrip("/")

    def upload(
        self,
        *,
        setup_job_id: str,
        source_document_id: str,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> str:
        storage_path = self._make_path(setup_job_id, source_document_id, filename)
        self._store[storage_path] = StoredObject(
            data=data,
            content_type=content_type,
            size_bytes=len(data),
            checksum=_sha256(data),
        )
        return storage_path

    def download(self, storage_path: str) -> StoredObject:
        if storage_path not in self._store:
            raise ObjectNotFoundError(storage_path)
        return self._store[storage_path]

    def exists(self, storage_path: str) -> bool:
        return storage_path in self._store

    def delete(self, storage_path: str) -> None:
        if storage_path not in self._store:
            raise ObjectNotFoundError(storage_path)
        del self._store[storage_path]

    def presigned_url(self, storage_path: str, expires_in: int = 3600) -> str:
        # В реальном MinIO здесь генерируется подписанная URL с TTL.
        # Для in-memory возвращаем стабильный псевдо-URL.
        if storage_path not in self._store:
            raise ObjectNotFoundError(storage_path)
        return f"{self._base_url}/{storage_path}?expires_in={expires_in}"

    def list_paths(self, prefix: str | None = None) -> list[str]:
        if prefix is None:
            return sorted(self._store.keys())
        return sorted(p for p in self._store if p.startswith(prefix))

    @classmethod
    def _make_path(
        cls, setup_job_id: str, source_document_id: str, filename: str
    ) -> str:
        # Path layout совпадает с MinIO layout из INF-003.
        safe_name = filename.replace("/", "_").replace("\\", "_")
        return f"s3://{cls.BUCKET}/{setup_job_id}/{source_document_id}/{safe_name}"

    def clear(self) -> None:
        """Для тестов."""
        self._store.clear()
