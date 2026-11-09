"""Taxonomy read-only API (SETUP-12 / T-S12-070).

Endpoints:
- GET /api/v1/taxonomy/versions          — список версий + активная.
- GET /api/v1/taxonomy/versions/{vid}/tree  — полное дерево версии.
- GET /api/v1/taxonomy/tree              — дерево активной версии.

Все endpoints требуют permission ``KB_TAXONOMY_READ`` (есть у user,
expert, rag_admin, admin, auditor — read-only).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyVersion,
)

from fe_bot.api.dependencies import (
    get_taxonomy_registry,
    require_permission,
)
from fe_bot.api.setup.taxonomy_dto import (
    TaxonomyNodeDTO,
    TaxonomyTreeNodeDTO,
    TaxonomyTreeResponse,
    TaxonomyVersionDTO,
    TaxonomyVersionListResponse,
)
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import Principal
from fe_bot.taxonomy import (
    NoActiveTaxonomyVersionError,
    TaxonomyRegistry,
)

router = APIRouter(prefix="/api/v1/taxonomy", tags=["taxonomy"])


# ----------------------------------------------------------------------
# GET /taxonomy/versions
# ----------------------------------------------------------------------


@router.get(
    "/versions",
    response_model=TaxonomyVersionListResponse,
    summary="List taxonomy versions (T-S12-070)",
)
def list_versions(
    _principal: Principal = Depends(require_permission(Permission.KB_TAXONOMY_READ)),
    registry: TaxonomyRegistry = Depends(get_taxonomy_registry),
) -> TaxonomyVersionListResponse:
    try:
        active = registry.get_active_version()
    except NoActiveTaxonomyVersionError:
        return TaxonomyVersionListResponse(versions=[], active_version_id=None)
    return TaxonomyVersionListResponse(
        versions=[_version_to_dto(active)],
        active_version_id=active.version_id,
    )


# ----------------------------------------------------------------------
# GET /taxonomy/tree (active version shortcut)
# ----------------------------------------------------------------------


@router.get(
    "/tree",
    response_model=TaxonomyTreeResponse,
    summary="Get active taxonomy tree (T-S12-070)",
)
def get_active_tree(
    _principal: Principal = Depends(require_permission(Permission.KB_TAXONOMY_READ)),
    registry: TaxonomyRegistry = Depends(get_taxonomy_registry),
) -> TaxonomyTreeResponse:
    try:
        active = registry.get_active_version()
    except NoActiveTaxonomyVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active taxonomy version (taxonomy not bootstrapped)",
        ) from exc
    return _build_tree_response(registry, active)


# ----------------------------------------------------------------------
# GET /taxonomy/versions/{version_id}/tree
# ----------------------------------------------------------------------


@router.get(
    "/versions/{version_id}/tree",
    response_model=TaxonomyTreeResponse,
    summary="Get taxonomy tree for a specific version (T-S12-070)",
)
def get_version_tree(
    version_id: str = Path(..., min_length=1),
    _principal: Principal = Depends(require_permission(Permission.KB_TAXONOMY_READ)),
    registry: TaxonomyRegistry = Depends(get_taxonomy_registry),
) -> TaxonomyTreeResponse:
    # MVP: registry хранит активную + созданные patch-bump'ом версии,
    # но публично через TaxonomyRegistry виден только active. Если
    # запрашивают другой version_id — 404 (admin UI получит позже).
    try:
        active = registry.get_active_version()
    except NoActiveTaxonomyVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Taxonomy version {version_id!r} not found",
        ) from exc
    if active.version_id != version_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Taxonomy version {version_id!r} not found (active: "
                f"{active.version_id!r}). Non-active versions read API"
                " not yet exposed (TD-HTC-002)."
            ),
        )
    return _build_tree_response(registry, active)


# ----------------------------------------------------------------------
# Internal builders
# ----------------------------------------------------------------------


def _build_tree_response(
    registry: TaxonomyRegistry, version: TaxonomyVersion
) -> TaxonomyTreeResponse:
    l0_entries = registry.list_active_under(
        version_id=version.version_id, level=0, parent_path=""
    )
    roots: list[TaxonomyTreeNodeDTO] = []
    total = 0
    auto_created = 0
    for l0 in l0_entries:
        l0_node = _entry_to_dto(l0)
        l1_children: list[TaxonomyTreeNodeDTO] = []
        l1_entries = registry.list_active_under(
            version_id=version.version_id,
            level=1,
            parent_path=l0.class_slug,
        )
        for l1 in l1_entries:
            l1_node = _entry_to_dto(l1)
            l2_children: list[TaxonomyTreeNodeDTO] = []
            l2_entries = registry.list_active_under(
                version_id=version.version_id,
                level=2,
                parent_path=f"{l0.class_slug}.{l1.class_slug}",
            )
            for l2 in l2_entries:
                l2_node = _entry_to_dto(l2)
                l2_children.append(
                    TaxonomyTreeNodeDTO(node=l2_node, children=[])
                )
                if l2.auto_created:
                    auto_created += 1
                total += 1
            l1_children.append(
                TaxonomyTreeNodeDTO(node=l1_node, children=l2_children)
            )
            if l1.auto_created:
                auto_created += 1
            total += 1
        roots.append(
            TaxonomyTreeNodeDTO(node=l0_node, children=l1_children)
        )
        if l0.auto_created:
            auto_created += 1
        total += 1
    return TaxonomyTreeResponse(
        version=_version_to_dto(version),
        roots=roots,
        total_classes=total,
        auto_created_count=auto_created,
    )


def _entry_to_dto(entry: TaxonomyBitRegistryEntry) -> TaxonomyNodeDTO:
    return TaxonomyNodeDTO(
        version_id=entry.version_id,
        level=entry.level,
        parent_path=entry.parent_path,
        bit_index=entry.bit_index,
        class_slug=entry.class_slug,
        display_name_ru=entry.display_name_ru,
        display_name_en=entry.display_name_en,
        description=entry.description,
        doc_type_hint=entry.doc_type_hint,
        auto_created=entry.auto_created,
        usage_count=entry.usage_count,
    )


def _version_to_dto(version: TaxonomyVersion) -> TaxonomyVersionDTO:
    return TaxonomyVersionDTO(
        version_id=version.version_id,
        created_at=version.created_at,
        description=version.description,
        is_active=version.is_active,
    )
