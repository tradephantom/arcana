"""Internal validation helpers for public ARCANA typed contracts."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, TypeVar

from arcana.errors import ArcanaValidationError, PathPart, ReasonCode, ValidationIssue


SHA256_RE = re.compile(r"^sha256:[A-Fa-f0-9]{64}$")
RISK_MODEL_RE = re.compile(r"^arcana\.risk\.v[0-9]+\.[0-9]+(\.[0-9]+)?$")
CALIBRATION_PROFILE_RE = re.compile(r"^arcana\.cal\.[A-Za-z0-9_.:-]+$")
CERTIFICATE_ID_RE = re.compile(r"^arcana-cert-[A-Za-z0-9_.:-]+$")
SCENARIO_ID_RE = re.compile(r"^arcana-bench-[A-Za-z0-9_.:-]+$")

T = TypeVar("T")


def issue(
    code: str,
    reason_code: ReasonCode,
    message: str,
    path: Sequence[PathPart] = (),
) -> ValidationIssue:
    return ValidationIssue(code=code, reason_code=reason_code, message=message, path=tuple(path))


def fail(
    code: str,
    reason_code: ReasonCode,
    message: str,
    path: Sequence[PathPart] = (),
) -> None:
    raise ArcanaValidationError(issue(code, reason_code, message, path))


def expect_mapping(value: Any, path: Sequence[PathPart], reason_code: ReasonCode) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        fail("object_expected", reason_code, "expected object", path)
    return value


def require_value(
    mapping: Mapping[str, Any],
    key: str,
    path: Sequence[PathPart],
    reason_code: ReasonCode,
) -> Any:
    if key not in mapping:
        fail("required_field_missing", reason_code, f"{key} is required", (*path, key))
    return mapping[key]


def expect_non_empty_string(
    value: Any,
    path: Sequence[PathPart],
    reason_code: ReasonCode,
    code: str = "string_invalid",
) -> str:
    if not isinstance(value, str) or not value:
        fail(code, reason_code, "expected non-empty string", path)
    return value


def expect_bool(value: Any, path: Sequence[PathPart], reason_code: ReasonCode) -> bool:
    if not isinstance(value, bool):
        fail("boolean_invalid", reason_code, "expected boolean", path)
    return value


def expect_int_min(value: Any, minimum: int, path: Sequence[PathPart], reason_code: ReasonCode) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        fail("integer_invalid", reason_code, f"expected integer >= {minimum}", path)
    return value


def expect_number_min(value: Any, minimum: float, path: Sequence[PathPart], reason_code: ReasonCode) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or float(value) < minimum:
        fail("number_invalid", reason_code, f"expected finite number >= {minimum}", path)
    return float(value)


def expect_number_range(
    value: Any,
    minimum: float,
    maximum: float,
    path: Sequence[PathPart],
    reason_code: ReasonCode,
) -> float:
    number = expect_number_min(value, minimum, path, reason_code)
    if number > maximum:
        fail("number_out_of_range", reason_code, f"expected number <= {maximum}", path)
    return number


def expect_enum(enum_type: type[T], value: Any, path: Sequence[PathPart], reason_code: ReasonCode) -> T:
    if not isinstance(value, str):
        fail("enum_invalid", reason_code, "expected string enum value", path)
    try:
        return enum_type(value)  # type: ignore[misc, call-arg]
    except ValueError:
        fail("enum_invalid", reason_code, f"unsupported enum value {value!r}", path)


def expect_string_list(
    value: Any,
    path: Sequence[PathPart],
    reason_code: ReasonCode,
    min_items: int = 0,
    unique: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        fail("array_invalid", reason_code, "expected array", path)
    if len(value) < min_items:
        fail("array_too_short", reason_code, f"expected at least {min_items} item(s)", path)
    normalized: list[str] = []
    for index, item in enumerate(value):
        normalized.append(expect_non_empty_string(item, (*path, index), reason_code))
    if unique and len(normalized) != len(set(normalized)):
        fail("array_not_unique", reason_code, "expected unique string values", path)
    return tuple(normalized)


def expect_sha256(value: Any, path: Sequence[PathPart], reason_code: ReasonCode) -> str:
    text = expect_non_empty_string(value, path, reason_code, "sha256_hash_invalid")
    if not SHA256_RE.match(text):
        fail("sha256_hash_invalid", reason_code, "expected sha256:<64 hex chars>", path)
    return text


def expect_risk_model_version(value: Any, path: Sequence[PathPart]) -> str:
    text = expect_non_empty_string(value, path, ReasonCode.DENY_RISK_MODEL_UNSUPPORTED, "risk_model_version_invalid")
    if not RISK_MODEL_RE.match(text):
        fail("risk_model_version_invalid", ReasonCode.DENY_RISK_MODEL_UNSUPPORTED, "unsupported risk model version syntax", path)
    return text


def expect_calibration_profile_id(value: Any, path: Sequence[PathPart]) -> str:
    text = expect_non_empty_string(value, path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "calibration_profile_id_invalid")
    if not CALIBRATION_PROFILE_RE.match(text):
        fail("calibration_profile_id_invalid", ReasonCode.DENY_CALIBRATION_INSUFFICIENT, "invalid calibration profile id", path)
    return text


def expect_certificate_id(value: Any, path: Sequence[PathPart]) -> str:
    text = expect_non_empty_string(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID, "certificate_id_invalid")
    if not CERTIFICATE_ID_RE.match(text):
        fail("certificate_id_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "invalid certificate id", path)
    return text


def expect_scenario_id(value: Any, path: Sequence[PathPart]) -> str:
    text = expect_non_empty_string(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID, "scenario_id_invalid")
    if not SCENARIO_ID_RE.match(text):
        fail("scenario_id_invalid", ReasonCode.DENY_MODEL_INPUT_INVALID, "invalid benchmark scenario id", path)
    return text


def expect_datetime_string(value: Any, path: Sequence[PathPart], reason_code: ReasonCode) -> str:
    text = expect_non_empty_string(value, path, reason_code, "datetime_invalid")
    normalized = text.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        fail("datetime_invalid", reason_code, "expected RFC3339-compatible date-time", path)
    return text


__all__ = [
    "CALIBRATION_PROFILE_RE",
    "CERTIFICATE_ID_RE",
    "RISK_MODEL_RE",
    "SCENARIO_ID_RE",
    "SHA256_RE",
    "expect_bool",
    "expect_calibration_profile_id",
    "expect_certificate_id",
    "expect_datetime_string",
    "expect_enum",
    "expect_int_min",
    "expect_mapping",
    "expect_non_empty_string",
    "expect_number_min",
    "expect_number_range",
    "expect_risk_model_version",
    "expect_scenario_id",
    "expect_sha256",
    "expect_string_list",
    "fail",
    "issue",
    "require_value",
]
