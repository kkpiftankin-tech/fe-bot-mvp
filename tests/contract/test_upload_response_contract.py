"""Contract: UploadDocumentsResponse v2 OpenAPI schema (T-S02-010).

Проверяет, что описание схемы в OpenAPI совпадает с реальной structure
ответа. Любое изменение DTO (добавление/удаление поля) должно либо:
1. быть осознанным контракт-breaking change → bump DTO версии, или
2. сохранять backward compatibility (добавление optional полей).

Также проверяет error_code enum: значения должны быть стабильными string'ами.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemas.setup.upload_errors import UploadErrorCode

from fe_bot.app import create_app

pytestmark = pytest.mark.unit


@pytest.fixture
def openapi_spec() -> dict:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    return resp.json()


def _find_schema(spec: dict, name: str) -> dict:
    schemas = spec["components"]["schemas"]
    assert name in schemas, f"Schema {name!r} not found in OpenAPI spec"
    return schemas[name]


class TestUploadDocumentsResponseSchema:
    def test_response_schema_present_in_openapi(
        self, openapi_spec: dict
    ) -> None:
        schema = _find_schema(openapi_spec, "UploadDocumentsResponse")
        # 8 fields в v2.
        properties = schema["properties"]
        expected_fields = {
            "setup_job_id",
            "upload_batch_id",
            "summary",
            "uploaded",
            "skipped_duplicates",
            "errors",
            "job_status",
            "message",
        }
        assert expected_fields.issubset(properties.keys()), (
            f"Missing fields: {expected_fields - properties.keys()}"
        )

    def test_response_extra_forbid(self, openapi_spec: dict) -> None:
        schema = _find_schema(openapi_spec, "UploadDocumentsResponse")
        # Pydantic с extra="forbid" → additionalProperties=false.
        assert schema.get("additionalProperties") is False

    def test_summary_schema_present(self, openapi_spec: dict) -> None:
        schema = _find_schema(openapi_spec, "UploadSummary")
        properties = schema["properties"]
        assert {
            "files_total",
            "files_uploaded",
            "files_rejected",
            "duplicates_detected",
        }.issubset(properties.keys())
        # counters все required и ge=0.
        for field in (
            "files_total",
            "files_uploaded",
            "files_rejected",
            "duplicates_detected",
        ):
            assert properties[field].get("minimum") == 0
        assert set(schema["required"]) == {
            "files_total",
            "files_uploaded",
            "files_rejected",
            "duplicates_detected",
        }


class TestUploadFileErrorSchema:
    def test_error_schema_present(self, openapi_spec: dict) -> None:
        schema = _find_schema(openapi_spec, "UploadFileError")
        properties = schema["properties"]
        assert {"filename", "error_code", "message", "details"}.issubset(
            properties.keys()
        )

    def test_error_code_is_enum_with_stable_values(
        self, openapi_spec: dict
    ) -> None:
        schema = _find_schema(openapi_spec, "UploadErrorCode")
        # Все enum-значения из контракта.
        enum_values = set(schema["enum"])
        expected = {code.value for code in UploadErrorCode}
        assert enum_values == expected, (
            f"OpenAPI enum mismatch: missing {expected - enum_values}, "
            f"extra {enum_values - expected}"
        )


class TestUploadDocumentsEndpointDescription:
    def test_post_endpoint_exists(self, openapi_spec: dict) -> None:
        paths = openapi_spec["paths"]
        endpoint = paths["/api/v1/setup/{setup_job_id}/documents"]
        assert "post" in endpoint

    def test_post_accepts_query_params(self, openapi_spec: dict) -> None:
        paths = openapi_spec["paths"]
        endpoint = paths["/api/v1/setup/{setup_job_id}/documents"]["post"]
        params = {p["name"] for p in endpoint.get("parameters", [])}
        # T-S02-007: upload_request_id для idempotency.
        assert "upload_request_id" in params
        # T-S01-013: duplicate_strategy.
        assert "duplicate_strategy" in params

    def test_post_returns_upload_documents_response(
        self, openapi_spec: dict
    ) -> None:
        paths = openapi_spec["paths"]
        endpoint = paths["/api/v1/setup/{setup_job_id}/documents"]["post"]
        # 201 Created — основной ответ.
        responses = endpoint["responses"]
        assert "201" in responses
        content = responses["201"]["content"]["application/json"]
        ref = content["schema"]["$ref"]
        assert ref.endswith("/UploadDocumentsResponse")


class TestBackwardCompatibilityWithV1:
    def test_v1_fields_still_present(self, openapi_spec: dict) -> None:
        """v1-клиенты SETUP-01 продолжают работать: uploaded и skipped_duplicates
        не удалены, только дополнены."""
        schema = _find_schema(openapi_spec, "UploadDocumentsResponse")
        properties = schema["properties"]
        assert "uploaded" in properties
        assert "skipped_duplicates" in properties
        # job_status (v1) тоже остался.
        assert "job_status" in properties

    def test_new_v2_fields_are_optional(
        self, openapi_spec: dict
    ) -> None:
        """summary, upload_batch_id, errors — расширения, optional с дефолтами."""
        schema = _find_schema(openapi_spec, "UploadDocumentsResponse")
        required = set(schema.get("required", []))
        # v2-поля не в required → v1-клиенты могут не передавать их.
        assert "upload_batch_id" not in required
        assert "summary" not in required
        # `errors` имеет default_factory=list → не в required.
        assert "errors" not in required
