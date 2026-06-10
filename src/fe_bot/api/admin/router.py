"""Admin router (SETUP-02 / T-S02-023).

Endpoints для административных операций:
- POST /admin/cleanup/orphans — найти/удалить orphan-файлы в Artifact Storage.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from fe_bot.api.dependencies import (
    get_orphan_cleanup_service,
    require_permission,
)
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import Principal
from fe_bot.setup.upload.cleanup import OrphanCleanupService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class CleanupOrphansResponse(BaseModel):
    """Сводка cleanup-операции."""

    model_config = ConfigDict(extra="forbid")

    dry_run: bool
    total_storage_paths: int
    total_registered_paths: int
    orphans_found: int
    deleted: int
    orphan_paths: list[str]
    deleted_paths: list[str]
    errors: list[str]
    message: str | None = None


@router.post(
    "/cleanup/orphans",
    response_model=CleanupOrphansResponse,
    summary="Find/delete orphan files (T-S02-023)",
)
def cleanup_orphans(
    dry_run: bool = Query(
        default=True,
        description=(
            "True — только перечислить orphans, не удалять (default). "
            "False — удалить найденные orphans."
        ),
    ),
    setup_job_id: str | None = Query(
        default=None,
        description="Если указан — scope cleanup только этим job'ом.",
    ),
    ignore_min_age: bool = Query(
        default=False,
        description=(
            "True — удалять объекты независимо от возраста (опасно). "
            "False — применять TTL-фильтр."
        ),
    ),
    principal: Principal = Depends(require_permission(Permission.KB_ADMIN_CLEANUP)),
    cleanup_svc: OrphanCleanupService = Depends(get_orphan_cleanup_service),
) -> CleanupOrphansResponse:
    """Находит storage-объекты, не привязанные к SourceRegistry, и удаляет их.

    **Только admin** (`KB_ADMIN_CLEANUP`).

    Безопасно по умолчанию (`dry_run=true`) — возвращает список orphans без удаления.
    """
    setup_job_ids = [setup_job_id] if setup_job_id else None
    result = cleanup_svc.cleanup(
        dry_run=dry_run,
        setup_job_ids=setup_job_ids,
        ignore_min_age=ignore_min_age,
    )

    message = None
    if dry_run:
        message = f"Dry run: found {len(result.orphan_paths)} orphan(s); none deleted."
    else:
        message = (
            f"Deleted {len(result.deleted_paths)} orphan(s); "
            f"errors: {len(result.errors)}"
        )

    return CleanupOrphansResponse(
        dry_run=result.dry_run,
        total_storage_paths=result.total_storage_paths,
        total_registered_paths=result.total_registered_paths,
        orphans_found=len(result.orphan_paths),
        deleted=len(result.deleted_paths),
        orphan_paths=result.orphan_paths,
        deleted_paths=result.deleted_paths,
        errors=result.errors,
        message=message,
    )
    _ = principal  # silence unused (auth уже сработал через Depends)
