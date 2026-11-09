"""SETUP-08 chunking API endpoints (T-S08-012).

4 endpoints под /api/v1/setup/{setup_job_id}/...:

- POST /chunking/run                    — batch chunking
- GET  /chunking/manifest               — latest manifest
- GET  /chunking/preview/{doc_id}       — preview без persistence
- POST /chunking/refresh/{doc_id}       — re-chunk одной карточки
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status
from schemas.rag.chunk import Chunk

from fe_bot.api.dependencies import (
    get_card_registry,
    get_chunk_manifest_repo,
    get_chunking_orchestrator,
    get_orchestrator,
    require_permission,
)
from fe_bot.api.setup.chunking_dto import (
    ChunkingRunResponse,
    ChunkItemDTO,
    ChunkManifestResponse,
    ChunkPreviewResponse,
    RunChunkingRequest,
)
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import Principal
from fe_bot.setup.card_registry.service import (
    CardNotFoundError,
    InMemoryRAGCardRegistry,
)
from fe_bot.setup.chunking.manifest_repository import (
    InMemoryChunkManifestRepository,
)
from fe_bot.setup.chunking.orchestrator import ChunkingOrchestrator
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.repository import JobNotFoundError

router = APIRouter(prefix="/api/v1/setup", tags=["chunking"])


_CROSS_JOB_PERMISSIONS = (Permission.KB_PUBLISH, Permission.KB_CARD_REVIEW)


def _check_job_access(job, principal: Principal) -> None:
    if job.user_id == principal.user_id:
        return
    if any(principal.has_permission(p) for p in _CROSS_JOB_PERMISSIONS):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot access chunking of another user's setup job",
    )


def _load_setup_job(
    *,
    orchestrator: SetupOrchestrator,
    setup_job_id: str,
    principal: Principal,
):
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _check_job_access(job, principal)
    return job


def _chunk_to_dto(chunk: Chunk) -> ChunkItemDTO:
    return ChunkItemDTO(
        chunk_id=chunk.chunk_id,
        doc_id=chunk.doc_id,
        chunk_type=chunk.chunk_type.value,
        section_title=chunk.section_title,
        chunk_text=chunk.chunk_text,
        embedding_text=chunk.embedding_text,
        metadata=chunk.metadata,
        priority=chunk.priority,
        source_section_id=chunk.source_section_id,
        token_count=chunk.token_count,
        created_at=chunk.created_at,
        status=chunk.status.value,
    )


@router.post(
    "/{setup_job_id}/chunking/run",
    response_model=ChunkingRunResponse,
    summary="Run batch chunking (T-S08-012)",
)
def run_chunking(
    payload: RunChunkingRequest | None = None,
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_CHUNKING_RUN)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    chunking_orch: ChunkingOrchestrator = Depends(get_chunking_orchestrator),
) -> ChunkingRunResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    run = chunking_orch.run_for_job(setup_job_id, triggered_by=principal.user_id)
    return ChunkingRunResponse(
        chunking_run_id=run.chunking_run_id,
        setup_job_id=run.setup_job_id,
        manifest_id=run.manifest_id,
        triggered_by=run.triggered_by,
        total_cards=run.total_cards,
        chunks_created=run.chunks_created,
        duration_ms=run.duration_ms,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get(
    "/{setup_job_id}/chunking/manifest",
    response_model=ChunkManifestResponse,
    summary="Get latest chunk manifest (T-S08-012)",
)
def get_manifest(
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_CHUNKING_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    manifest_repo: InMemoryChunkManifestRepository = Depends(get_chunk_manifest_repo),
) -> ChunkManifestResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    manifest = manifest_repo.get_latest_for_job(setup_job_id)
    if manifest is None:
        raise HTTPException(
            status_code=404,
            detail=f"No chunk manifest for setup_job {setup_job_id!r}",
        )
    return ChunkManifestResponse(
        manifest_id=manifest.manifest_id,
        setup_job_id=manifest.setup_job_id,
        total_chunks=manifest.total_chunks,
        by_type=manifest.by_type,
        chunks=[_chunk_to_dto(c) for c in manifest.chunks],
        created_at=manifest.created_at,
        created_by=manifest.created_by,
    )


@router.get(
    "/{setup_job_id}/chunking/preview/{doc_id}",
    response_model=ChunkPreviewResponse,
    summary="Preview chunks для одной карточки без persistence (T-S08-012)",
)
def preview_chunks(
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_CHUNKING_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    chunking_orch: ChunkingOrchestrator = Depends(get_chunking_orchestrator),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> ChunkPreviewResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    try:
        rec = card_registry.get(doc_id)
    except CardNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if rec.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=404,
            detail=f"Card {doc_id!r} not found in setup_job {setup_job_id!r}",
        )
    chunks = chunking_orch.preview_card(doc_id)
    return ChunkPreviewResponse(
        doc_id=doc_id,
        chunks=[_chunk_to_dto(c) for c in chunks],
    )


@router.post(
    "/{setup_job_id}/chunking/refresh/{doc_id}",
    response_model=ChunkPreviewResponse,
    summary="Re-chunk одну карточку (T-S08-012)",
)
def refresh_chunks(
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_CHUNKING_REFRESH)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    chunking_orch: ChunkingOrchestrator = Depends(get_chunking_orchestrator),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> ChunkPreviewResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    try:
        rec = card_registry.get(doc_id)
    except CardNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if rec.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=404,
            detail=f"Card {doc_id!r} not found in setup_job {setup_job_id!r}",
        )
    chunks = chunking_orch.refresh_card(doc_id, triggered_by=principal.user_id)
    return ChunkPreviewResponse(
        doc_id=doc_id,
        chunks=[_chunk_to_dto(c) for c in chunks],
    )
