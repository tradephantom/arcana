"""Public schema validation and typed fixture loading for ARCANA."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from arcana._resources import RESOURCE_ROOT
from arcana._validation import issue
from arcana.benchmark_input import BenchmarkExecutionSuite
from arcana.calibration import CalibrationProfile
from arcana.certificate import BoundedAutonomyCertificate
from arcana.errors import ArcanaValidationError, ReasonCode, SchemaVersion, ValidationIssue
from arcana.model import BenchmarkScenario, RiskContext


ROOT = RESOURCE_ROOT
SCHEMA_DIR = ROOT / "schemas"
EXAMPLE_DIR = ROOT / "examples"

SCHEMA_FILES: Mapping[SchemaVersion, str] = {
    SchemaVersion.CALIBRATION_PROFILE_V02: "ARCANA_CalibrationProfile.schema.v0.2.json",
    SchemaVersion.CONTEXT_V02: "ARCANA_Context.schema.v0.2.json",
    SchemaVersion.CERTIFICATE_V02: "ARCANA_Certificate.schema.v0.2.json",
    SchemaVersion.BENCHMARK_SCENARIO_V02: "ARCANA_BenchmarkScenario.schema.v0.2.json",
    SchemaVersion.BENCHMARK_EXECUTION_SUITE_V01: "ARCANA_BenchmarkExecutionSuite.schema.v0.1.json",
}

TypedDocument = CalibrationProfile | RiskContext | BoundedAutonomyCertificate | BenchmarkScenario | BenchmarkExecutionSuite


@dataclass(frozen=True)
class ValidatedDocument:
    schema_version: SchemaVersion
    data: Mapping[str, Any]
    source_path: Path | None = None


def load_json(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ArcanaValidationError(
            issue(
                "json_decode_error",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                f"invalid JSON: {exc.msg}",
                (str(path),),
            )
        ) from exc
    if not isinstance(data, Mapping):
        raise ArcanaValidationError(
            issue(
                "json_top_level_not_object",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "top-level JSON value must be an object",
                (str(path),),
            )
        )
    return data


def load_schema(schema_version: SchemaVersion) -> Mapping[str, Any]:
    schema_path = SCHEMA_DIR / SCHEMA_FILES[schema_version]
    return load_json(schema_path)


def detect_schema_version(document: Mapping[str, Any]) -> SchemaVersion:
    raw_version = document.get("schema_version")
    if not isinstance(raw_version, str) or not raw_version:
        raise ArcanaValidationError(
            issue(
                "schema_version_missing",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "schema_version is required",
                ("schema_version",),
            )
        )
    try:
        return SchemaVersion(raw_version)
    except ValueError as exc:
        raise ArcanaValidationError(
            issue(
                "schema_version_unsupported",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                f"unsupported schema_version {raw_version!r}",
                ("schema_version",),
            )
        ) from exc


def validate_document(
    document: Mapping[str, Any],
    schema_version: SchemaVersion | None = None,
    source_path: Path | None = None,
) -> ValidatedDocument:
    detected_version = schema_version or detect_schema_version(document)
    schema = load_schema(detected_version)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda item: (tuple(item.absolute_path), tuple(item.absolute_schema_path)))
    if errors:
        raise ArcanaValidationError(_schema_error_to_issue(error) for error in errors)
    return ValidatedDocument(schema_version=detected_version, data=document, source_path=source_path)


def load_fixture(path: Path, schema_version: SchemaVersion | None = None) -> ValidatedDocument:
    document = load_json(path)
    return validate_document(document, schema_version=schema_version, source_path=path)


def parse_typed_document(document: Mapping[str, Any], schema_version: SchemaVersion | None = None) -> TypedDocument:
    validated = validate_document(document, schema_version=schema_version)
    return _parse_validated_document(validated)


def load_typed_fixture(path: Path, schema_version: SchemaVersion | None = None) -> TypedDocument:
    return _parse_validated_document(load_fixture(path, schema_version=schema_version))


def load_public_examples() -> tuple[TypedDocument, ...]:
    return tuple(load_typed_fixture(path) for path in sorted(EXAMPLE_DIR.glob("*.json")))


def _parse_validated_document(validated: ValidatedDocument) -> TypedDocument:
    if validated.schema_version is SchemaVersion.CALIBRATION_PROFILE_V02:
        return CalibrationProfile.from_mapping(validated.data)
    if validated.schema_version is SchemaVersion.CONTEXT_V02:
        return RiskContext.from_mapping(validated.data)
    if validated.schema_version is SchemaVersion.CERTIFICATE_V02:
        return BoundedAutonomyCertificate.from_mapping(validated.data)
    if validated.schema_version is SchemaVersion.BENCHMARK_SCENARIO_V02:
        return BenchmarkScenario.from_mapping(validated.data)
    if validated.schema_version is SchemaVersion.BENCHMARK_EXECUTION_SUITE_V01:
        return BenchmarkExecutionSuite.from_mapping(validated.data)
    raise ArcanaValidationError(
        issue(
            "schema_version_unsupported",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            f"unsupported schema_version {validated.schema_version.value!r}",
            ("schema_version",),
        )
    )


def _schema_error_to_issue(error: ValidationError) -> ValidationIssue:
    path = tuple(error.absolute_path)
    missing = _missing_required_property(error)
    issue_path = (*path, missing) if missing is not None else path
    return issue(
        code=_schema_error_code(error, missing),
        reason_code=_reason_code_for_error(error, missing),
        message=error.message,
        path=issue_path,
    )


def _missing_required_property(error: ValidationError) -> str | None:
    if error.validator != "required":
        return None
    if isinstance(error.instance, Mapping):
        missing = [key for key in error.validator_value if key not in error.instance]
        if len(missing) == 1:
            return str(missing[0])
    match = re.match(r"'([^']+)' is a required property", error.message)
    return match.group(1) if match else None


def _schema_error_code(error: ValidationError, missing: str | None) -> str:
    target = missing or (str(error.path[-1]) if error.path else "document")
    return f"schema_{error.validator}_{target}"


def _reason_code_for_error(error: ValidationError, missing: str | None) -> ReasonCode:
    path = tuple(str(part) for part in error.absolute_path)
    target = missing or (path[-1] if path else "")
    scope = set(path)
    if target == "schema_version":
        return ReasonCode.DENY_MODEL_INPUT_INVALID
    if target == "risk_model_version":
        return ReasonCode.DENY_RISK_MODEL_UNSUPPORTED
    if target == "decision_horizon" or "decision_horizon" in scope or target in {"id", "duration_seconds", "context"} and "decision_horizon" in scope:
        return ReasonCode.DENY_DECISION_HORIZON_MISMATCH
    if target in {"graph_hash", "request_graph_hash", "matrix_graph_hash"} or scope.intersection({"graph_hash", "request_graph_hash", "matrix_graph_hash"}):
        return ReasonCode.DENY_GRAPH_HASH_MISMATCH
    if target in {
        "calibration_profile",
        "calibration_profile_id",
        "calibration_level",
        "profile_id",
        "level",
        "source",
        "confidence",
        "certification_status",
        "evidence_window",
        "edge_weight_policy",
    } or "calibration_profile" in scope or "evidence_window" in scope or "edge_weight_policy" in scope:
        return ReasonCode.DENY_CALIBRATION_INSUFFICIENT
    if target == "evidence" or "evidence" in scope:
        return ReasonCode.DENY_CALIBRATION_INSUFFICIENT
    if target == "autonomy_budget" or "autonomy_budget" in scope:
        return ReasonCode.DENY_BUDGET_EXHAUSTED
    if target == "loss_bounds" or "loss_bounds" in scope or target.startswith("aar_") or target.startswith("aes_") or target.startswith("max_allowed_"):
        return ReasonCode.DENY_LOSS_MODEL_INVALID
    if target == "positive_vector_method":
        return ReasonCode.DENY_FASTGATE_VECTOR_INVALID
    if target == "upper_bound" and "fastgate" in scope:
        return ReasonCode.DENY_FASTGATE_UNCERTAIN
    if target == "fastgate" or "fastgate" in scope or target == "mode":
        return ReasonCode.DENY_FASTGATE_VECTOR_INVALID
    if target in {"issued_at", "expires_at", "last_updated_at"}:
        return ReasonCode.DENY_CONTEXT_STALE
    if target in {"rho_interval", "uncertainty", "rho_lower", "rho_mean", "rho_upper", "lower", "mean", "upper", "threshold"}:
        return ReasonCode.DENY_MODEL_INPUT_INVALID
    return ReasonCode.DENY_MODEL_INPUT_INVALID


__all__ = [
    "EXAMPLE_DIR",
    "ROOT",
    "SCHEMA_DIR",
    "SCHEMA_FILES",
    "TypedDocument",
    "ValidatedDocument",
    "detect_schema_version",
    "load_fixture",
    "load_json",
    "load_public_examples",
    "load_schema",
    "load_typed_fixture",
    "parse_typed_document",
    "validate_document",
]
