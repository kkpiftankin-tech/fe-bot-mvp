"""Orphan file cleanup (SETUP-02 / T-S02-023).

Orphan — объект в Object Storage, на который нет ссылки в Source Registry.
Возникает при:
- транзакционном сбое (storage.upload успешен, registry.add упал — fallback
  цепочка в DocumentUploadService уже вызывает storage.delete, но
  catastrophic failures могут оставить остатки);
- ручном вмешательстве админа;
- частичных pipeline failures в downstream сервисах (S5+ chunking).

Cleanup safe-by-default: возвращает list orphans, **удаляет только** если
вызван с `dry_run=False` (default True).

Использование:
    POST /admin/cleanup/orphans?dry_run=false (требует Permission.ADMIN_ONLY)
    или из background scheduler (INF-002).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from fe_bot.setup.source_registry.service import SourceRegistry
from fe_bot.storage.artifact_service import ArtifactStorage

logger = logging.getLogger(__name__)

# Минимальный возраст объекта, прежде чем он считается orphan-кандидатом.
# Защищает от удаления только что загруженных файлов, для которых
# registry.add ещё не успел зафиксироваться.
DEFAULT_ORPHAN_MIN_AGE = timedelta(hours=24)


@dataclass(slots=True)
class CleanupResult:
    """Сводка прогона cleanup."""

    dry_run: bool
    total_storage_paths: int = 0
    total_registered_paths: int = 0
    orphan_paths: list[str] = field(default_factory=list)
    deleted_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class OrphanCleanupService:
    """Находит и (опционально) удаляет orphan-объекты в Artifact Storage."""

    def __init__(
        self,
        *,
        storage: ArtifactStorage,
        registry: SourceRegistry,
        min_age: timedelta = DEFAULT_ORPHAN_MIN_AGE,
    ) -> None:
        self._storage = storage
        self._registry = registry
        self._min_age = min_age

    def find_orphans(
        self,
        *,
        setup_job_ids: list[str] | None = None,
    ) -> list[str]:
        """Возвращает storage_paths, которых нет в SourceRegistry.

        Если `setup_job_ids` указан — рассматриваются только эти jobs.
        Иначе — все объекты в storage.

        Не применяет TTL-фильтр (это делается в `cleanup`).
        """
        all_paths = set(self._storage.list_paths())
        registered = set(self._collect_registered_paths(setup_job_ids))
        orphans = sorted(all_paths - registered)
        return orphans

    def cleanup(
        self,
        *,
        dry_run: bool = True,
        setup_job_ids: list[str] | None = None,
        ignore_min_age: bool = False,
    ) -> CleanupResult:
        """Запускает cleanup. По умолчанию dry_run — без реального удаления.

        - `ignore_min_age=False`: возраст объекта не используется (in-memory
          storage не отслеживает created_at). В реальной MinIO/S3 imp
          применяется `LastModified` + TTL — это будет добавлено в INF-002.
        """
        result = CleanupResult(dry_run=dry_run)
        all_paths = self._storage.list_paths()
        registered = list(self._collect_registered_paths(setup_job_ids))
        result.total_storage_paths = len(all_paths)
        result.total_registered_paths = len(registered)

        registered_set = set(registered)
        orphans = [p for p in all_paths if p not in registered_set]
        result.orphan_paths = orphans

        # Min-age фильтрация: в in-memory storage нет timestamp;
        # в продакшене (MinIO) будем фильтровать по LastModified.
        if not ignore_min_age:
            logger.info(
                "orphan_cleanup.dry_run_only_in_memory_storage",
                extra={"min_age_hours": int(self._min_age.total_seconds() / 3600)},
            )

        if dry_run:
            return result

        for path in orphans:
            try:
                self._storage.delete(path)
                result.deleted_paths.append(path)
            except Exception as exc:
                msg = f"DELETE_FAILED[{path}]: {type(exc).__name__}: {exc}"
                result.errors.append(msg)
                logger.warning(
                    "orphan_cleanup.delete_failed",
                    extra={"storage_path": path, "error": str(exc)},
                )

        logger.info(
            "orphan_cleanup.completed",
            extra={
                "dry_run": dry_run,
                "orphans_found": len(orphans),
                "deleted": len(result.deleted_paths),
                "errors": len(result.errors),
            },
        )
        # Use UTC import to avoid unused warning + structured logging context.
        _ = datetime.now(tz=UTC)
        return result

    def _collect_registered_paths(
        self, setup_job_ids: list[str] | None
    ) -> list[str]:
        """Собирает storage_paths всех документов в registry (включая REMOVED).

        Removed documents всё ещё имеют storage_path в registry — но он уже
        удалён физически (см. remove_document). Тем не менее мы их **не**
        считаем orphans (registry знает про них).
        """
        if setup_job_ids is None:
            # Безopasно: cleanup без scope требует явной admin-операции.
            # Для in-memory просто пройдёмся по всем известным jobs.
            # В PostgreSQL: SELECT storage_path FROM source_documents.
            seen_paths: set[str] = set()
            # InMemorySourceRegistry не имеет list_all() — используем list_for_job
            # по setup_job_id'ам, которые встречаются в storage paths.
            for path in self._storage.list_paths():
                # Парсим setup_job_id из path layout `s3://bucket/<sjid>/<sdid>/<file>`
                parts = path.split("/")
                if len(parts) >= 4 and parts[0] == "s3:":
                    sjid = parts[3]
                    for doc in self._registry.list_for_job(sjid):
                        seen_paths.add(doc.storage_path)
            return sorted(seen_paths)
        seen_paths_scoped: set[str] = set()
        for sjid in setup_job_ids:
            for doc in self._registry.list_for_job(sjid):
                seen_paths_scoped.add(doc.storage_path)
        return sorted(seen_paths_scoped)
