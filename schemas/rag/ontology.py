"""Закрытые словари онтологии RAG-слоя.

Source of truth — docs/06-rag/ontology.md. Изменения требуют ADR.
"""

from __future__ import annotations

from enum import StrEnum


class Domain(StrEnum):
    NAVAL = "naval"
    AIR = "air"
    GROUND = "ground"
    CYBER = "cyber"
    ANALYTICAL = "analytical"
    CUSTOM = "custom"


class DataSource(StrEnum):
    RADAR = "radar"
    SONAR = "sonar"
    AIS = "AIS"
    ESM = "ESM"
    EO_IR = "EO_IR"
    SATELLITE = "satellite"
    TRACKS_FUSED = "tracks_fused"
    EXTERNAL_CONDITIONS = "external_conditions"
    TACTICAL_OBJECTS = "tactical_objects"
    SQL = "SQL"
    CSV = "CSV"
    JSON = "JSON"
    CUSTOM = "custom"


class TaskType(StrEnum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    ANOMALY_DETECTION = "anomaly_detection"
    RANKING = "ranking"
    TRAJECTORY_FORECASTING = "trajectory_forecasting"
    OBJECT_DETECTION = "object_detection"


class DataType(StrEnum):
    TABULAR = "tabular"
    TIME_SERIES = "time_series"
    IMAGE = "image"
    TENSOR = "tensor"
    GRAPH = "graph"
    EVENT_LOG = "event_log"
    MIXED = "mixed"


class FeatureFamily(StrEnum):
    KINEMATIC = "kinematic"
    RCS = "rcs"
    SIGNAL_QUALITY = "signal_quality"
    ACOUSTIC = "acoustic"
    ELECTRO_OPTICAL = "electro_optical"
    SENSOR_ANALYTICS = "sensor_analytics"
    WEAPON_ANALYTICS = "weapon_analytics"
    COMMS_ANALYTICS = "comms_analytics"
    OBJECT_STATE = "object_state"
    ENVIRONMENT = "environment"
    THREAT = "threat"
    CUSTOM = "custom"


class DocType(StrEnum):
    """Типы RAG-карточек (см. docs/06-rag/document-types.md)."""

    ONTOLOGY_CARD = "ontology_card"
    DOMAIN_PROFILE = "domain_profile"
    SCHEMA_CARD = "schema_card"
    FIELD_DEFINITION_CARD = "field_definition_card"
    TASK_CARD = "task_card"
    FEATURE_PATTERN_CARD = "feature_pattern_card"
    ANALYTICS_CARD = "analytics_card"
    VALIDATION_RULE_CARD = "validation_rule_card"
    QUESTION_TEMPLATE_CARD = "question_template_card"
    MODEL_RECOMMENDATION_CARD = "model_recommendation_card"
    GLOSSARY_TERM = "glossary_term"
    EXAMPLE_CARD = "example_card"
    BAD_EXAMPLE_CARD = "bad_example_card"


class Phase(StrEnum):
    """Фазы workflow (см. docs/04-domain/value-objects.md и rag-overview.md)."""

    NLU = "nlu"
    TASK_DISCOVERY = "task_discovery"
    DATA_PROFILING = "data_profiling"
    DOMAIN_CONTEXT = "domain_context"
    FEATURE_SYNTHESIS = "feature_synthesis"
    VALIDATION = "validation"
    DATA_GENERATION = "data_generation"
    MODEL_SELECTION = "model_selection"
    EXPORT = "export"
    ANALYTICS = "analytics"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Список известных агентов из AGENTS.md. Используется для валидации agent_targets.
KNOWN_AGENTS: frozenset[str] = frozenset(
    {
        "SessionAgent",
        "NLUAgent",
        "RAGRetrievalAgent",
        "DialogueOrchestratorAgent",
        "ContextMemoryAgent",
        "TaskDiscoveryAgent",
        "DataProfilingAgent",
        "DomainContextAgent",
        "FeatureSynthesisAgent",
        "FeatureCriticAgent",
        "MulticollinearityAgent",
        "DataGenerationSpecAgent",
        "ModelSelectionAgent",
        "ExportAgent",
        "FeedbackAgent",
        "AuditAgent",
    }
)
