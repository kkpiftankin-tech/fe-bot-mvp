"""Classifier Library API (SETUP-13 / ADR-HTC-09).

Endpoints:
- GET    /api/v1/classifier/tree                       — сводка (корни).
- GET    /api/v1/classifier/tree/nodes/{node_id}        — узел + дети + rendered prompt.
- POST   /api/v1/classifier/tree/nodes/{node_id}/children — создать дочерний класс.
- PATCH  /api/v1/classifier/tree/nodes/{node_id}        — переименовать/описание/prompt_override.
- DELETE /api/v1/classifier/tree/nodes/{node_id}        — удалить (каскадно детей).
- POST   /api/v1/classifier/tree/nodes/{node_id}/generate-description — черновик через LLM.

Read — ``KB_CLASSIFIER_READ``, mutating — ``KB_CLASSIFIER_WRITE``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status
from schemas.classifier.node import ClassifierNode
from schemas.classifier.tree import ClassifierTree

from fe_bot.api.dependencies import (
    get_classifier_description_generator,
    get_classifier_service,
    require_permission,
)
from fe_bot.api.setup.classifier_dto import (
    ClassifierNodeDetailsResponse,
    ClassifierNodeDTO,
    ClassifierTreeSummaryResponse,
    CreateChildNodeRequest,
    DeleteNodeResponse,
    GenerateDescriptionResponse,
    UpdateNodeRequest,
)
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import Principal
from fe_bot.classifier.description_generator import ClassifierDescriptionGenerator
from fe_bot.classifier.prompt_renderer import (
    ClassifierPromptRenderer,
    NodeHasNoChildrenError,
)
from fe_bot.classifier.tree_repository import NoActiveTreeError
from fe_bot.classifier.tree_service import (
    _UNSET,
    ClassifierTreeService,
    NodeNotFoundError,
    RootDeletionError,
    _Unset,
)
from fe_bot.llm_gateway.exceptions import InvalidLLMOutputError, LLMUnavailableError

router = APIRouter(prefix="/api/v1/classifier", tags=["classifier"])

_renderer = ClassifierPromptRenderer()


def _node_to_dto(tree: ClassifierTree, node: ClassifierNode) -> ClassifierNodeDTO:
    return ClassifierNodeDTO(
        node_id=node.node_id,
        parent_id=node.parent_id,
        level=node.level,
        name=node.name,
        description=node.description,
        children_ids=node.children_ids,
        prompt_override=node.prompt_override,
        is_leaf=node.is_leaf,
        path=tree.get_path(node.node_id),
    )


def _get_active_tree(service: ClassifierTreeService) -> ClassifierTree:
    try:
        return service.get_active_tree()
    except NoActiveTreeError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active classifier tree (library not bootstrapped)",
        ) from exc


@router.get(
    "/tree",
    response_model=ClassifierTreeSummaryResponse,
    summary="Get active classifier tree summary (SETUP-13)",
)
def get_tree_summary(
    _principal: Principal = Depends(require_permission(Permission.KB_CLASSIFIER_READ)),
    service: ClassifierTreeService = Depends(get_classifier_service),
) -> ClassifierTreeSummaryResponse:
    tree = _get_active_tree(service)
    roots = [_node_to_dto(tree, tree.nodes[rid]) for rid in tree.root_ids]
    return ClassifierTreeSummaryResponse(
        tree_id=tree.tree_id,
        version=tree.version,
        description=tree.description,
        total_nodes=len(tree.nodes),
        roots=roots,
    )


@router.get(
    "/tree/nodes/{node_id}",
    response_model=ClassifierNodeDetailsResponse,
    summary="Get one node + its children + rendered prompt (SETUP-13)",
)
def get_node(
    node_id: str = Path(..., min_length=1),
    _principal: Principal = Depends(require_permission(Permission.KB_CLASSIFIER_READ)),
    service: ClassifierTreeService = Depends(get_classifier_service),
) -> ClassifierNodeDetailsResponse:
    tree = _get_active_tree(service)
    if node_id not in tree.nodes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Node not found: {node_id}"
        )
    node = tree.nodes[node_id]
    children = [_node_to_dto(tree, tree.nodes[cid]) for cid in node.children_ids]
    rendered_prompt: str | None = None
    if not node.is_leaf:
        try:
            rendered_prompt = _renderer.render(tree, node_id)
        except NodeHasNoChildrenError:
            rendered_prompt = None
    return ClassifierNodeDetailsResponse(
        node=_node_to_dto(tree, node), children=children, rendered_prompt=rendered_prompt
    )


@router.post(
    "/tree/nodes/{node_id}/children",
    response_model=ClassifierNodeDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Add a child class under a node (SETUP-13)",
)
def create_child(
    payload: CreateChildNodeRequest,
    node_id: str = Path(..., min_length=1),
    _principal: Principal = Depends(require_permission(Permission.KB_CLASSIFIER_WRITE)),
    service: ClassifierTreeService = Depends(get_classifier_service),
) -> ClassifierNodeDTO:
    tree = _get_active_tree(service)
    try:
        updated = service.add_child(
            tree.tree_id, parent_id=node_id, name=payload.name, description=payload.description
        )
    except NodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    parent = updated.nodes[node_id]
    new_child_id = parent.children_ids[-1]
    return _node_to_dto(updated, updated.nodes[new_child_id])


@router.patch(
    "/tree/nodes/{node_id}",
    response_model=ClassifierNodeDTO,
    summary="Update a node's name/description/prompt_override (SETUP-13)",
)
def update_node(
    payload: UpdateNodeRequest,
    node_id: str = Path(..., min_length=1),
    _principal: Principal = Depends(require_permission(Permission.KB_CLASSIFIER_WRITE)),
    service: ClassifierTreeService = Depends(get_classifier_service),
) -> ClassifierNodeDTO:
    tree = _get_active_tree(service)
    prompt_override: str | None | _Unset = _UNSET
    if payload.clear_prompt_override:
        prompt_override = None
    elif payload.prompt_override is not None:
        prompt_override = payload.prompt_override
    try:
        updated = service.update_node(
            tree.tree_id,
            node_id,
            name=payload.name,
            description=payload.description,
            prompt_override=prompt_override,
        )
    except NodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _node_to_dto(updated, updated.nodes[node_id])


@router.delete(
    "/tree/nodes/{node_id}",
    response_model=DeleteNodeResponse,
    summary="Delete a node and its descendants (SETUP-13)",
)
def delete_node(
    node_id: str = Path(..., min_length=1),
    _principal: Principal = Depends(require_permission(Permission.KB_CLASSIFIER_WRITE)),
    service: ClassifierTreeService = Depends(get_classifier_service),
) -> DeleteNodeResponse:
    tree = _get_active_tree(service)
    before = len(tree.nodes)
    try:
        updated = service.delete_node(tree.tree_id, node_id)
    except NodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RootDeletionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    deleted_count = before - len(updated.nodes)
    return DeleteNodeResponse(
        node_id=node_id,
        deleted_count=deleted_count,
        message=f"Deleted {node_id} and {deleted_count - 1} descendant(s)",
    )


@router.post(
    "/tree/nodes/{node_id}/generate-description",
    response_model=GenerateDescriptionResponse,
    summary="Draft a class description via a small LLM (SETUP-13)",
)
def generate_description(
    node_id: str = Path(..., min_length=1),
    _principal: Principal = Depends(require_permission(Permission.KB_CLASSIFIER_WRITE)),
    service: ClassifierTreeService = Depends(get_classifier_service),
    generator: ClassifierDescriptionGenerator = Depends(get_classifier_description_generator),
) -> GenerateDescriptionResponse:
    tree = _get_active_tree(service)
    if node_id not in tree.nodes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Node not found: {node_id}"
        )
    node = tree.nodes[node_id]
    try:
        description = generator.generate(name=node.name, path=tree.get_path(node_id))
    except (LLMUnavailableError, InvalidLLMOutputError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM unavailable for description generation: {exc}",
        ) from exc
    return GenerateDescriptionResponse(description=description)
