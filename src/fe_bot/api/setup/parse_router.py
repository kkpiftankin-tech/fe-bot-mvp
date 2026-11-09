"""SETUP-04 Parse endpoints (T-S04-023..026).

6 endpoints под /api/v1/setup/{setup_job_id}/parse-jobs:
- POST   /parse-jobs                                 — создать ParseJob
- GET    /parse-jobs/{parse_job_id}                  — статус
- GET    /parse-jobs/{parse_job_id}/report           — отчёт по документам
- GET    /parse-jobs/{parse_job_id}/sections         — список секций
- POST   /parse-jobs/{parse_job_id}/cancel           — cancel job
- POST   /parse-jobs/{parse_job_id}/documents/{src_id}/retry — retry упавшего документа
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from schemas.setup.parse_job import (
    InvalidParseJobTransitionError,
    ParseErrorCode,
    ParseJob,
    ParseJobStatus,
)
from schemas.setup.parse_job_document import ParseJobDocumentStatus
from schemas.setup.parsed_section import (
    ParsedSection,
    ParsedSectionStatus,
    SectionType,
)
from schemas.setup.rag_setup_job import RAGSetupJob

from fe_bot.api.dependencies import (
    get_document_parser_orchestrator,
    get_orchestrator,
    get_parse_document_repo,
    get_parse_job_repo,
    get_parse_report_repo,
    get_parsed_section_repo,
    require_permission,
)
from fe_bot.api.setup.parse_dto import (
    CancelParseJobResponse,
    ClassificationBitDTO,
    ClassificationPromptDTO,
    CreateParseJobRequest,
    DocumentReportDTO,
    PaginationDTO,
    ParsedSectionDetailDTO,
    ParsedSectionListItemDTO,
    ParsedSectionsResponse,
    ParseJobReportResponse,
    ParseJobResponse,
    RetryParseDocumentResponse,
)
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import Principal
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.parser.document_repository import (
    InMemoryParseJobDocumentRepository,
    ParseJobDocumentNotFoundError,
)
from fe_bot.setup.parser.job_repository import (
    InMemoryParseJobRepository,
    ParseJobNotFoundError,
)
from fe_bot.setup.parser.orchestrator import (
    DocumentParserOrchestrator,
    NoParseableDocumentsError,
    ParseJobAlreadyRunningError,
)
from fe_bot.setup.parser.report_repository import (
    InMemoryDocumentParseReportRepository,
)
from fe_bot.setup.parser.section_repository import (
    InMemoryParsedSectionRepository,
)
from fe_bot.setup.repository import JobNotFoundError

router = APIRouter(prefix="/api/v1/setup", tags=["parse"])

_CROSS_JOB_PERMISSIONS = (Permission.KB_PUBLISH, Permission.KB_CARD_REVIEW)

# Запас на случай более глубоких деревьев классификаторов, чем текущие 6
# уровней (asu_v1.txt) — тот же запас, что FragmentClassifier._DEFAULT_MAX_LEVELS.
_DEFAULT_MAX_PROMPT_LEVELS = 10


# ============================================================
# Helpers
# ============================================================


def _check_job_access(job: RAGSetupJob, principal: Principal) -> None:
    if job.user_id == principal.user_id:
        return
    if any(principal.has_permission(p) for p in _CROSS_JOB_PERMISSIONS):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot access parse jobs of another user's setup job",
    )


def _load_job(
    *,
    orchestrator: SetupOrchestrator,
    setup_job_id: str,
    principal: Principal,
) -> RAGSetupJob:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _check_job_access(job, principal)
    return job


def _load_parse_job(*, parse_job_repo: InMemoryParseJobRepository, parse_job_id: str) -> ParseJob:
    try:
        return parse_job_repo.get(parse_job_id)
    except ParseJobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _ensure_parse_job_in_setup(parse_job: ParseJob, setup_job_id: str) -> None:
    if parse_job.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"ParseJob {parse_job.parse_job_id!r} does not belong to setup_job {setup_job_id!r}"
            ),
        )


def _to_parse_job_response(job: ParseJob) -> ParseJobResponse:
    return ParseJobResponse(
        parse_job_id=job.parse_job_id,
        setup_job_id=job.setup_job_id,
        status=job.status,
        total_documents=job.total_documents,
        processed_documents=job.processed_documents,
        failed_documents=job.failed_documents,
        total_sections=job.total_sections,
        low_confidence_sections=job.low_confidence_sections,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_code=job.error_code,
        error_message=job.error_message,
    )


def _build_section_detail(section: ParsedSection) -> ParsedSectionDetailDTO:
    """Полная детализация секции + расшифровка bitmap'а через реестр."""
    from fe_bot.api.dependencies import (
        _taxonomy_mode,
        get_taxonomy_registry,
    )

    cs_dict = (
        section.classification_state.model_dump()
        if section.classification_state is not None
        else None
    )
    bits: list[ClassificationBitDTO] = []
    if (
        section.classification_state is not None
        and _taxonomy_mode() == "llm"
    ):
        try:
            registry = get_taxonomy_registry()
            bits = _resolve_classification_bits(
                section.classification_state, registry
            )
        except Exception:  # noqa: BLE001 — best-effort enrichment
            pass
    return ParsedSectionDetailDTO(
        section_id=section.section_id,
        parse_job_id=section.parse_job_id,
        source_document_id=section.source_document_id,
        title=section.title,
        heading_path=list(section.heading_path),
        section_index=section.section_index,
        parent_section_id=section.parent_section_id,
        section_type=section.section_type,
        section_status=section.section_status,
        confidence=section.confidence,
        content_hash=section.content_hash,
        raw_text=section.raw_text,
        normalized_text=section.normalized_text,
        start_offset=section.start_offset,
        end_offset=section.end_offset,
        metadata=dict(section.metadata or {}),
        classification_method=section.classification_method,
        classification_state=cs_dict,
        classification_bits=bits,
        classifier_result=section.classifier_result,
    )


def _resolve_classification_bits(
    state, registry
) -> list[ClassificationBitDTO]:  # noqa: ANN001 — local helper
    """Расшифровывает bitmap каждого set-бита через taxonomy_bit_registry."""
    from schemas.taxonomy.state import BITS_PER_LEVEL

    out: list[ClassificationBitDTO] = []
    version_id = state.taxonomy_version_id
    # Resolve primary L0 slug для parent_path L1.
    primary_l0_slug: str | None = None
    if state.primary_l0_idx is not None:
        try:
            entry = registry.get_by_bit(
                version_id=version_id,
                level=0,
                parent_path="",
                bit_index=state.primary_l0_idx,
            )
            primary_l0_slug = entry.class_slug
        except Exception:  # noqa: BLE001
            primary_l0_slug = None
    primary_l1_slug: str | None = None
    if state.primary_l1_idx is not None and primary_l0_slug is not None:
        try:
            entry = registry.get_by_bit(
                version_id=version_id,
                level=1,
                parent_path=primary_l0_slug,
                bit_index=state.primary_l1_idx,
            )
            primary_l1_slug = entry.class_slug
        except Exception:  # noqa: BLE001
            primary_l1_slug = None

    for level in range(3):
        bits = state.bits_at(level)
        for bit in bits:
            parent_path = ""
            if level == 1:
                parent_path = primary_l0_slug or ""
            elif level == 2:
                parent_path = (
                    f"{primary_l0_slug}.{primary_l1_slug}"
                    if primary_l0_slug and primary_l1_slug
                    else ""
                )
            if level >= 1 and not parent_path:
                continue  # bit некому расшифровать (broken state)
            try:
                entry = registry.get_by_bit(
                    version_id=version_id,
                    level=level,
                    parent_path=parent_path,
                    bit_index=bit,
                )
            except Exception:  # noqa: BLE001
                continue
            is_primary = (
                (level == 0 and bit == state.primary_l0_idx)
                or (level == 1 and bit == state.primary_l1_idx)
                or (
                    level == 2
                    and len(state.bits_at(2)) == 1
                    and bit == bits[0]
                )
            )
            conf_key = f"{level}:{bit}"
            conf = state.confidence_per_bit.get(conf_key)
            out.append(
                ClassificationBitDTO(
                    level=level,
                    bit_index=bit,
                    class_slug=entry.class_slug,
                    display_name_ru=entry.display_name_ru,
                    doc_type_hint=entry.doc_type_hint,
                    confidence=conf,
                    is_primary=is_primary,
                )
            )
    _ = BITS_PER_LEVEL  # для явного importа-проверки
    return out


def _build_prompt_previews(section: ParsedSection) -> list[ClassificationPromptDTO]:
    """Возвращает preview промптов, которыми классифицируется секция.

    SETUP-13 (ADR-HTC-09): активный классификатор — дерево произвольной
    глубины (``ClassifierTreeService`` / ``ClassifierPromptRenderer``), а
    не legacy 3-уровневый L0/L1/L2 bitmap (SETUP-12, ``fe_bot.taxonomy.*``).
    Раньше эта функция рендерила промпты ИСКЛЮЧИТЕЛЬНО через legacy-реестр
    и ``section.classification_state`` — для секций, классифицированных
    деревом (``classifier_result`` заполнен, ``classification_state`` —
    нет), это давало prompt preview от СОВСЕМ ДРУГОГО (legacy) дерева
    классов, не имеющего отношения к тому, что реально видела LLM.

    Воспроизводит фактический путь обхода ``FragmentClassifier.classify()``
    по ``section.classifier_result.path`` (или только корень, если секция
    ещё не классифицирована) и рендерит промпт на каждом уровне этого пути
    текущим ``ClassifierPromptRenderer`` + текущим активным деревом. Это не
    исторический prompt (не сохраняется), а «как бы выглядел запрос
    сейчас» — полезно для отладки и понимания, что видит LLM.
    """
    from fe_bot.api.dependencies import _taxonomy_mode, get_classifier_service

    if _taxonomy_mode() != "llm":
        return [
            ClassificationPromptDTO(
                level=0,
                parent_path="",
                candidates_count=0,
                free_slots_count=0,
                rendered_prompt="",
                can_render=False,
                reason="Taxonomy mode is 'rule_based' — no LLM prompts.",
            )
        ]

    from fe_bot.classifier.prompt_renderer import ClassifierPromptRenderer
    from fe_bot.classifier.tree_repository import NoActiveTreeError

    tree_service = get_classifier_service()
    try:
        tree = tree_service.get_active_tree()
    except NoActiveTreeError:
        return [
            ClassificationPromptDTO(
                level=0,
                parent_path="",
                candidates_count=0,
                free_slots_count=0,
                rendered_prompt="",
                can_render=False,
                reason="Нет активного дерева классификаторов (SETUP-13).",
            )
        ]
    if not tree.root_ids:
        return [
            ClassificationPromptDTO(
                level=0,
                parent_path="",
                candidates_count=0,
                free_slots_count=0,
                rendered_prompt="",
                can_render=False,
                reason="Активное дерево классификаторов пусто.",
            )
        ]

    section_text = section.normalized_text or section.raw_text or "(empty)"
    path_steps = iter(section.classifier_result.path if section.classifier_result else [])
    renderer = ClassifierPromptRenderer()
    out: list[ClassificationPromptDTO] = []

    # Воспроизводим тот же обход, что FragmentClassifier.classify() делал
    # (или сделал бы) реально: на каждом нелистовом узле рендерится промпт,
    # затем спускаемся к выбранному на этом уровне ребёнку (по
    # classifier_result.path). Останавливаемся на листе или там, где путь
    # закончился (LLM не выбрала ребёнка / остановилась по confidence) —
    # то есть рендерим ровно те уровни, на которых реально был/будет вызов LLM.
    current_id = tree.root_ids[0]
    for level in range(_DEFAULT_MAX_PROMPT_LEVELS):
        node = tree.nodes.get(current_id)
        if node is None or node.is_leaf:
            break
        children = tree.get_children(current_id)
        try:
            rendered = renderer.render(tree, current_id, fragment_text=section_text)
            out.append(
                ClassificationPromptDTO(
                    level=level,
                    parent_path=" → ".join(tree.get_path(current_id)),
                    candidates_count=len(children),
                    free_slots_count=0,
                    rendered_prompt=rendered,
                    can_render=True,
                )
            )
        except Exception as exc:  # noqa: BLE001
            out.append(
                ClassificationPromptDTO(
                    level=level,
                    parent_path=" → ".join(tree.get_path(current_id)),
                    candidates_count=len(children),
                    free_slots_count=0,
                    rendered_prompt="",
                    can_render=False,
                    reason=f"Renderer failed: {exc}",
                )
            )
        step = next(path_steps, None)
        if step is None or step.node_id not in {c.node_id for c in children}:
            break
        current_id = step.node_id
    return out


def _to_section_list_item(section: ParsedSection) -> ParsedSectionListItemDTO:
    # SETUP-12: сериализуем classification_state как dict (frontend читает
    # optional field). None для rule_based mode.
    cs_dict = (
        section.classification_state.model_dump()
        if section.classification_state is not None
        else None
    )
    return ParsedSectionListItemDTO(
        section_id=section.section_id,
        source_document_id=section.source_document_id,
        title=section.title,
        section_type=section.section_type,
        section_status=section.section_status,
        confidence=section.confidence,
        heading_path=list(section.heading_path),
        section_index=section.section_index,
        parent_section_id=section.parent_section_id,
        content_hash=section.content_hash,
        classification_method=section.classification_method,
        classification_state=cs_dict,
        classifier_result=section.classifier_result,
    )


def _paginate[T](items: list[T], page: int, page_size: int) -> tuple[list[T], PaginationDTO]:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], PaginationDTO(page=page, page_size=page_size, total=total)


# ============================================================
# T-S04-023: POST /parse-jobs
# ============================================================


@router.post(
    "/{setup_job_id}/parse-jobs",
    response_model=ParseJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ParseJob (T-S04-023)",
)
def create_parse_job(
    payload: CreateParseJobRequest,
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PARSE_RUN)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parser_orchestrator: DocumentParserOrchestrator = Depends(get_document_parser_orchestrator),
) -> ParseJobResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    try:
        job = parser_orchestrator.create_parse_job(
            setup_job_id=setup_job_id,
            requested_by=principal.user_id,
            config=payload.config,
        )
    except ParseJobAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": ParseErrorCode.PARSE_JOB_ALREADY_RUNNING.value,
                "message": str(exc),
                "active_parse_job_id": exc.active_parse_job_id,
            },
        ) from exc
    except NoParseableDocumentsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ParseErrorCode.NO_PARSEABLE_DOCUMENTS.value,
                "message": str(exc),
            },
        ) from exc
    return _to_parse_job_response(job)


# ============================================================
# Run ParseJob synchronously (T-S04-020/023 — UI/CLI trigger).
# ============================================================


@router.post(
    "/{setup_job_id}/parse-jobs/{parse_job_id}/run",
    response_model=ParseJobResponse,
    summary="Run ParseJob synchronously (T-S04-020)",
)
def run_parse_job(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PARSE_RUN)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parser_orchestrator: DocumentParserOrchestrator = Depends(get_document_parser_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
) -> ParseJobResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)
    if job.is_terminal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "PARSE_JOB_TERMINAL",
                "message": f"ParseJob is in terminal state {job.status.value}",
                "current_status": job.status.value,
            },
        )
    final = parser_orchestrator.run(parse_job_id)

    # SETUP-01 UX: авто-продвижение setup_job после завершения парсинга,
    # чтобы прогресс на главной корректно отражал реальное состояние
    # (иначе setup_job'ы с успешным парсингом застревают на 5%).
    _sync_setup_job_after_parse(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        parse_final=final,
    )

    return _to_parse_job_response(final)


def _sync_setup_job_after_parse(
    *,
    orchestrator: SetupOrchestrator,
    setup_job_id: str,
    parse_final: object,
) -> None:
    """Продвигает setup_job из FILES_UPLOADED → SECTIONS_EXTRACTED
    (или → FAILED). Тихо игнорирует ошибки (advance идемпотентен —
    повторные вызовы для уже-продвинутого job'а безопасны).
    """
    from schemas.setup.rag_setup_job import SetupJobStatus

    try:
        current_job = orchestrator.get_job(setup_job_id)
    except Exception:
        return
    # Не откатываем прогресс: если уже дальше SECTIONS_EXTRACTED — не трогаем.
    if current_job.status != SetupJobStatus.FILES_UPLOADED:
        return

    pj_status = getattr(parse_final, "status", None)
    pj_status_value = pj_status.value if pj_status is not None else ""
    total_sections = getattr(parse_final, "total_sections", 0)

    try:
        if pj_status_value in {"completed", "partial_success"} and total_sections > 0:
            orchestrator.advance(
                setup_job_id,
                SetupJobStatus.SECTIONS_EXTRACTED,
                message=f"Extracted {total_sections} section(s)",
                metrics={"sections_total": total_sections},
            )
        elif pj_status_value == "failed":
            orchestrator.advance(
                setup_job_id,
                SetupJobStatus.FAILED,
                message="Parse job failed",
            )
    except Exception:  # noqa: BLE001 — advance transition может быть невалидным
        # (напр. state machine не разрешает переход); просто пропускаем.
        pass


# ============================================================
# T-S04-024: GET status + report
# ============================================================


@router.get(
    "/{setup_job_id}/parse-jobs/{parse_job_id}",
    response_model=ParseJobResponse,
    summary="Get ParseJob status (T-S04-024)",
)
def get_parse_job_status(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PARSE_STATUS_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
) -> ParseJobResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)
    return _to_parse_job_response(job)


@router.get(
    "/{setup_job_id}/parse-jobs/{parse_job_id}/report",
    response_model=ParseJobReportResponse,
    summary="Get ParseJob report (T-S04-024)",
)
def get_parse_job_report(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PARSE_STATUS_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
    report_repo: InMemoryDocumentParseReportRepository = Depends(get_parse_report_repo),
) -> ParseJobReportResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)
    reports = report_repo.list_for_job(parse_job_id)
    documents = [
        DocumentReportDTO(
            source_document_id=r.source_document_id,
            status=r.status,
            parser_strategy=r.parser_strategy,
            sections_count=r.summary.sections_count,
            sections_by_type=dict(r.summary.sections_by_type),
            low_confidence_sections=r.summary.low_confidence_sections,
            errors=list(r.errors),
            warnings=list(r.warnings),
            created_at=r.created_at,
        )
        for r in reports
    ]
    return ParseJobReportResponse(
        parse_job_id=parse_job_id,
        setup_job_id=setup_job_id,
        status=job.status,
        documents=documents,
    )


# ============================================================
# T-S04-025: GET sections + POST cancel
# ============================================================


@router.get(
    "/{setup_job_id}/parse-jobs/{parse_job_id}/sections",
    response_model=ParsedSectionsResponse,
    summary="List parsed sections (T-S04-025)",
)
def list_parsed_sections(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    source_document_id: str | None = Query(default=None, min_length=1),
    section_type: SectionType | None = Query(default=None),
    section_status: ParsedSectionStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_permission(Permission.KB_SECTION_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
    section_repo: InMemoryParsedSectionRepository = Depends(get_parsed_section_repo),
) -> ParsedSectionsResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)

    sections = section_repo.list_for_job(parse_job_id)
    if source_document_id is not None:
        sections = [s for s in sections if s.source_document_id == source_document_id]
    if section_type is not None:
        sections = [s for s in sections if s.section_type == section_type]
    if section_status is not None:
        sections = [s for s in sections if s.section_status == section_status]

    paged, pagination = _paginate(sections, page, page_size)
    return ParsedSectionsResponse(
        parse_job_id=parse_job_id,
        items=[_to_section_list_item(s) for s in paged],
        pagination=pagination,
    )


# ============================================================
# SETUP-04 UX: детализация секции + preview LLM-prompts
# ============================================================


@router.get(
    "/{setup_job_id}/parse-jobs/{parse_job_id}/sections/{section_id}",
    response_model=ParsedSectionDetailDTO,
    summary="Get full section detail (raw + normalized text, classification)",
)
def get_section_detail(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    section_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_SECTION_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
    section_repo: InMemoryParsedSectionRepository = Depends(get_parsed_section_repo),
) -> ParsedSectionDetailDTO:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)
    try:
        section = section_repo.get(section_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_id!r} not found: {exc}",
        ) from exc
    if section.parse_job_id != parse_job_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_id!r} does not belong to parse_job {parse_job_id!r}",
        )
    return _build_section_detail(section)


@router.get(
    "/{setup_job_id}/parse-jobs/{parse_job_id}/sections/{section_id}/prompts",
    response_model=list[ClassificationPromptDTO],
    summary="Preview LLM classification prompts for a section (all levels)",
)
def get_section_prompts(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    section_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_SECTION_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
    section_repo: InMemoryParsedSectionRepository = Depends(get_parsed_section_repo),
) -> list[ClassificationPromptDTO]:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)
    try:
        section = section_repo.get(section_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_id!r} not found: {exc}",
        ) from exc
    if section.parse_job_id != parse_job_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_id!r} does not belong to parse_job {parse_job_id!r}",
        )
    return _build_prompt_previews(section)


@router.post(
    "/{setup_job_id}/parse-jobs/{parse_job_id}/cancel",
    response_model=CancelParseJobResponse,
    summary="Cancel ParseJob (T-S04-025)",
)
def cancel_parse_job(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PARSE_CANCEL)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
) -> CancelParseJobResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)

    try:
        job.transition_to(ParseJobStatus.CANCELLED)
    except InvalidParseJobTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "PARSE_JOB_TERMINAL",
                "message": str(exc),
                "current_status": job.status.value,
            },
        ) from exc
    parse_job_repo.update(job)
    return CancelParseJobResponse(
        parse_job_id=job.parse_job_id,
        status=job.status,
        message=f"ParseJob {parse_job_id} cancelled",
    )


# ============================================================
# T-S04-026: POST retry document
# ============================================================


@router.post(
    "/{setup_job_id}/parse-jobs/{parse_job_id}/documents/{source_document_id}/retry",
    response_model=RetryParseDocumentResponse,
    summary="Retry failed document (T-S04-026)",
)
def retry_parse_document(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    source_document_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PARSE_RETRY)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parser_orchestrator: DocumentParserOrchestrator = Depends(get_document_parser_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
    document_repo: InMemoryParseJobDocumentRepository = Depends(get_parse_document_repo),
) -> RetryParseDocumentResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)

    matched = [
        d
        for d in document_repo.list_for_job(parse_job_id)
        if d.source_document_id == source_document_id
    ]
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(f"Document {source_document_id!r} not in parse_job {parse_job_id!r}"),
        )
    target_doc = matched[-1]
    if target_doc.status != ParseJobDocumentStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": ParseErrorCode.DOCUMENT_NOT_PARSEABLE_STATUS.value,
                "message": (f"Document status is {target_doc.status.value}; retry only for FAILED"),
            },
        )

    # MVP-стратегия: создаём новый ParseJob для одного документа,
    # это упрощает rollback и аудит — не мутируем counters старого job'а.
    try:
        new_job = parser_orchestrator.create_parse_job(
            setup_job_id=setup_job_id,
            requested_by=principal.user_id,
            config={"retry_of": parse_job_id, "source_document_id": source_document_id},
        )
    except ParseJobAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": ParseErrorCode.PARSE_JOB_ALREADY_RUNNING.value,
                "message": str(exc),
                "active_parse_job_id": exc.active_parse_job_id,
            },
        ) from exc
    except NoParseableDocumentsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ParseErrorCode.NO_PARSEABLE_DOCUMENTS.value,
                "message": str(exc),
            },
        ) from exc
    return RetryParseDocumentResponse(
        parse_job_id=parse_job_id,
        source_document_id=source_document_id,
        status=ParseJobDocumentStatus.PENDING,
        message=f"Retry queued via new ParseJob {new_job.parse_job_id}",
        new_parse_job_id=new_job.parse_job_id,
    )


# Re-export of error classes for tests that want to introspect.
__all__ = [
    "ParseJobDocumentNotFoundError",
    "router",
]
