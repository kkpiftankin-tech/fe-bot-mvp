"""SETUP-05 RAG Cards Generation services.

Структура (по SETUP-04 parser/ как эталон):
- job_repository: RAGCardGenerationJob + state machine + active-job lock.
- job_section_repository: per-section записи внутри job.
- source_link_repository: lineage relations parsed_section → rag_card.
- report_repository: CardGenerationReport (last-write-wins по job_id).

Остальные компоненты (orchestrator, ontology_mapper, prompt_registry,
doc_type_detector, metadata_extractor, doc_id_generator, llm_adapter,
markdown_builder, precheck, confidence_calculator) — в S2..S4.
"""
