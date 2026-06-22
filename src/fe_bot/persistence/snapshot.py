"""Lightweight JSON snapshot persistence for dev.

Идея: на startup читаем ``var/state/snapshot.json`` + blob'ы из
``var/state/blobs/`` и заливаем в in-memory репозитории; на shutdown
сохраняем обратно. После каждого write полезно дописывать (debounced),
но в MVP — только границы lifecycle.

В проде эти репо заменятся на PostgreSQL/MinIO и модуль будет no-op.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

DEFAULT_STATE_DIR = Path(os.environ.get("FE_BOT_STATE_DIR", "var/state"))
SNAPSHOT_FILENAME = "snapshot.json"
BLOBS_DIRNAME = "blobs"


class _RepoLike(Protocol):
    def snapshot(self) -> dict[str, Any]: ...
    def restore(self, data: dict[str, Any]) -> None: ...


class _ArtifactStorageLike(Protocol):
    def snapshot(self) -> dict[str, Any]: ...
    def all_blobs(self) -> dict[str, bytes]: ...
    def restore(self, meta: dict[str, Any], blobs: dict[str, bytes]) -> None: ...


class SnapshotPersister:
    """Координирует JSON-снапшот всех зарегистрированных репозиториев."""

    def __init__(self, state_dir: Path = DEFAULT_STATE_DIR) -> None:
        self._state_dir = state_dir
        self._snapshot_path = state_dir / SNAPSHOT_FILENAME
        self._blobs_dir = state_dir / BLOBS_DIRNAME
        self._repos: dict[str, _RepoLike] = {}
        self._artifact_storage: _ArtifactStorageLike | None = None
        self._artifact_storage_key: str | None = None
        self._save_lock = threading.Lock()

    def register_repo(self, key: str, repo: _RepoLike) -> None:
        self._repos[key] = repo

    def register_artifact_storage(self, key: str, storage: _ArtifactStorageLike) -> None:
        self._artifact_storage = storage
        self._artifact_storage_key = key

    # ----- IO -----

    def load(self) -> bool:
        """Возвращает True если что-то восстановилось."""
        if not self._snapshot_path.exists():
            return False
        try:
            with self._snapshot_path.open("r", encoding="utf-8") as f:
                snapshot = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read snapshot %s: %s", self._snapshot_path, exc)
            return False

        restored_any = False
        for key, repo in self._repos.items():
            data = snapshot.get(key)
            if not isinstance(data, dict):
                continue
            try:
                repo.restore(data)
                restored_any = True
            except Exception:  # noqa: BLE001 — restore не должен валить startup
                logger.exception("Failed to restore repo %s", key)

        # Artifact storage: bytes из blobs/.
        if self._artifact_storage is not None and self._artifact_storage_key is not None:
            meta = snapshot.get(self._artifact_storage_key, {})
            if isinstance(meta, dict):
                blobs = self._load_blobs(meta)
                try:
                    self._artifact_storage.restore(meta, blobs)
                    restored_any = True
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to restore artifact storage")

        if restored_any:
            logger.info("Restored state from %s", self._snapshot_path)
        return restored_any

    def save(self) -> None:
        with self._save_lock:
            payload: dict[str, Any] = {}
            for key, repo in self._repos.items():
                try:
                    payload[key] = repo.snapshot()
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to snapshot repo %s", key)
            if self._artifact_storage is not None and self._artifact_storage_key is not None:
                try:
                    meta = self._artifact_storage.snapshot()
                    payload[self._artifact_storage_key] = meta
                    self._save_blobs(self._artifact_storage.all_blobs())
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to snapshot artifact storage")

            self._state_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = self._snapshot_path.with_suffix(".json.tmp")
            try:
                with tmp_path.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                tmp_path.replace(self._snapshot_path)
            except OSError:
                logger.exception("Failed to write snapshot")
                return
            logger.info("Saved snapshot to %s", self._snapshot_path)

    # ----- Blobs -----

    @staticmethod
    def _blob_filename(storage_path: str) -> str:
        # storage_path может быть s3://bucket/.../filename — заменяем небезопасные.
        digest = hashlib.sha256(storage_path.encode("utf-8")).hexdigest()[:16]
        safe = storage_path.replace("/", "_").replace(":", "_")[:120]
        return f"{digest}_{safe}.bin"

    def _save_blobs(self, blobs: dict[str, bytes]) -> None:
        self._blobs_dir.mkdir(parents=True, exist_ok=True)
        # Очистим устаревшие файлы — только те, что не в текущем snapshot.
        keep = {self._blob_filename(p) for p in blobs}
        for existing in self._blobs_dir.iterdir():
            if existing.is_file() and existing.name not in keep:
                existing.unlink(missing_ok=True)
        index: dict[str, str] = {}
        for storage_path, data in blobs.items():
            fname = self._blob_filename(storage_path)
            (self._blobs_dir / fname).write_bytes(data)
            index[storage_path] = fname
        # Index file (path → filename) для надёжного reload.
        (self._blobs_dir / "_index.json").write_text(
            json.dumps(index, ensure_ascii=False), encoding="utf-8"
        )

    def _load_blobs(self, meta: dict[str, Any]) -> dict[str, bytes]:
        blobs: dict[str, bytes] = {}
        index_path = self._blobs_dir / "_index.json"
        index: dict[str, str] = {}
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                index = {}
        for storage_path in meta:
            fname = index.get(storage_path) or self._blob_filename(storage_path)
            path = self._blobs_dir / fname
            if path.exists():
                try:
                    blobs[storage_path] = path.read_bytes()
                except OSError:
                    logger.warning("Failed to read blob %s", path)
        return blobs


def register_default_state(persister: SnapshotPersister) -> None:
    """Подключает persister к module-level singletons из api.dependencies."""
    from fe_bot.api import dependencies as deps

    persister.register_repo("setup_jobs", deps._job_repository)
    persister.register_repo("source_documents", deps._source_registry)
    persister.register_repo("parse_jobs", deps._parse_job_repo)
    persister.register_repo("parse_documents", deps._parse_doc_repo)
    persister.register_repo("parsed_sections", deps._parsed_section_repo)
    persister.register_repo("parse_reports", deps._parse_report_repo)
    # SETUP-05 (T-S05-025): RAG card generation state.
    persister.register_repo("rag_card_jobs", deps._rag_card_job_repo)
    persister.register_repo("rag_card_job_sections", deps._rag_card_section_repo)
    persister.register_repo("rag_card_source_links", deps._rag_card_source_link_repo)
    persister.register_repo("rag_card_generation_reports", deps._card_generation_report_repo)
    persister.register_repo("rag_cards_registry", deps._card_registry)
    persister.register_artifact_storage("artifacts", deps._artifact_storage)


# Helper for base64 encoding small inline blobs (not used today but kept for
# future flexibility — каждые ~1 МБ blob → 1.3 МБ base64).
def _b64(blob: bytes) -> str:
    return base64.b64encode(blob).decode("ascii")
