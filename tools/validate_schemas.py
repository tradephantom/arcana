#!/usr/bin/env python3
"""Validate ARCANA public schemas and synthetic examples."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
EXAMPLE_DIR = ROOT / "examples"
REASON_CODES_DOC = ROOT / "docs" / "REASON_CODES.md"

PUBLIC_SCHEMA_PREFIX = "https://arcana.tradephantom.com/schemas/"
SHA256_RE = re.compile(r"^sha256:[A-Fa-f0-9]{64}$")
RISK_MODEL_RE = re.compile(r"^arcana\.risk\.v[0-9]+\.[0-9]+(\.[0-9]+)?$")
CAL_PROFILE_RE = re.compile(r"^arcana\.cal\.[A-Za-z0-9_.:-]+$")
CERT_ID_RE = re.compile(r"^arcana-cert-[A-Za-z0-9_.:-]+$")
SCENARIO_ID_RE = re.compile(r"^arcana-bench-[A-Za-z0-9_.:-]+$")

SCHEMAS = {
    "arcana.calibration_profile.v0.2": "ARCANA_CalibrationProfile.schema.v0.2.json",
    "arcana.context.v0.2": "ARCANA_Context.schema.v0.2.json",
    "arcana.certificate.v0.2": "ARCANA_Certificate.schema.v0.2.json",
    "arcana.benchmark_scenario.v0.2": "ARCANA_BenchmarkScenario.schema.v0.2.json",
    "arcana.benchmark_execution_suite.v0.1": "ARCANA_BenchmarkExecutionSuite.schema.v0.1.json",
    "arcana.benchmark_run_report.v0.1": "ARCANA_BenchmarkRunReport.schema.v0.1.json",
}

VERDICTS = {
    "allow_bounded_autonomy",
    "allow_with_controls",
    "require_scope_reduction",
    "require_human_gate",
    "observe_only",
    "deny"
}

LEVELS = {"A0", "A1", "A2", "A3"}
FASTGATE_MODES = {"perron_collatz_bound", "exact_recompute", "observe_only"}
FASTGATE_POSITIVE_VECTOR_METHODS = {
    "irreducible_perron_vector",
    "scc_decomposition",
    "epsilon_floor",
    "component_local_gate",
    "fallback_exact",
}
EVIDENCE_SOURCE_TYPES = {
    "synthetic_fixture",
    "public_benchmark",
    "controlled_test",
    "hash_bound_context",
}
BENCHMARK_SCENARIO_TYPES = {
    "coverage_scenario",
    "negative_control",
}
BENCHMARK_NEGATIVE_CONTROLS = {
    "missing_decision_horizon",
    "graph_hash_mismatch",
    "a0_artifact_used_for_admission",
    "rho_mean_below_threshold_rho_upper_above_threshold",
    "fastgate_inconclusive",
    "loss_model_missing_required",
    "stale_evidence",
}


@dataclass(frozen=True)
class Finding:
    path: Path
    code: str
    detail: str


def rel(path: Path) -> Path:
    return path.relative_to(ROOT)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_registered_reason_codes() -> set[str]:
    text = REASON_CODES_DOC.read_text(encoding="utf-8")
    codes: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"\|\s*`(ARCANA_(?:ALLOW|DENY|REQUIRE|INFO)_[A-Z0-9_]+)`\s*\|", line)
        if match:
            codes.add(match.group(1))
    return codes


def require_keys(path: Path, obj: dict[str, Any], keys: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    missing = sorted(keys - set(obj))
    for key in missing:
        findings.append(Finding(rel(path), "missing_required_key", key))
    return findings


def check_schema_file(path: Path, schema: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(require_keys(path, schema, {"$schema", "$id", "title", "type", "required", "properties", "additionalProperties"}))

    schema_id = schema.get("$id")
    if not isinstance(schema_id, str) or not schema_id.startswith(PUBLIC_SCHEMA_PREFIX):
        findings.append(Finding(rel(path), "schema_id_not_public", str(schema_id)))
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        findings.append(Finding(rel(path), "schema_draft_mismatch", str(schema.get("$schema"))))
    if schema.get("type") != "object":
        findings.append(Finding(rel(path), "schema_type_not_object", str(schema.get("type"))))
    if schema.get("additionalProperties") is not False:
        findings.append(Finding(rel(path), "schema_top_level_allows_extra_properties", "additionalProperties must be false"))

    required = schema.get("required")
    if not isinstance(required, list) or "schema_version" not in required:
        findings.append(Finding(rel(path), "schema_version_not_required", "schema_version must be required"))

    properties = schema.get("properties")
    if isinstance(properties, dict):
        version = properties.get("schema_version", {}).get("const")
        expected_name = SCHEMAS.get(version)
        if expected_name is None:
            findings.append(Finding(rel(path), "unknown_schema_version_const", str(version)))
        elif expected_name != path.name:
            findings.append(Finding(rel(path), "schema_filename_mismatch", f"{version} should be {expected_name}"))

    return findings


def validate_reason_codes(path: Path, codes: Any, registered: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(codes, list) or not codes:
        return [Finding(rel(path), "reason_codes_invalid", "reason_codes must be a non-empty array")]
    for code in codes:
        if not isinstance(code, str):
            findings.append(Finding(rel(path), "reason_code_not_string", repr(code)))
        elif code not in registered:
            findings.append(Finding(rel(path), "reason_code_not_registered", code))
    if len(codes) != len(set(codes)):
        findings.append(Finding(rel(path), "reason_codes_not_unique", "duplicate reason code"))
    return findings


def validate_horizon(path: Path, horizon: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(horizon, dict):
        return [Finding(rel(path), "decision_horizon_invalid", "must be object")]
    findings.extend(require_keys(path, horizon, {"id", "duration_seconds", "context"}))
    if not isinstance(horizon.get("duration_seconds"), int) or horizon.get("duration_seconds", 0) < 1:
        findings.append(Finding(rel(path), "decision_horizon_duration_invalid", str(horizon.get("duration_seconds"))))
    return findings


def validate_evidence_window(path: Path, window: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(window, dict):
        return [Finding(rel(path), "evidence_window_invalid", "must be object")]
    findings.extend(require_keys(path, window, {"observed_after", "observed_before", "max_age_seconds"}))
    for key in ("observed_after", "observed_before"):
        if not isinstance(window.get(key), str) or not window.get(key):
            findings.append(Finding(rel(path), "evidence_window_time_invalid", f"{key}={window.get(key)!r}"))
    if not isinstance(window.get("max_age_seconds"), int) or window.get("max_age_seconds", 0) < 1:
        findings.append(Finding(rel(path), "evidence_window_max_age_invalid", str(window.get("max_age_seconds"))))
    return findings


def validate_rho_interval(path: Path, interval: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(interval, dict):
        return [Finding(rel(path), "rho_interval_invalid", "must be object")]
    findings.extend(require_keys(path, interval, {"lower", "mean", "upper", "threshold"}))
    for key in ("lower", "mean", "upper", "threshold"):
        value = interval.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            findings.append(Finding(rel(path), "rho_value_invalid", f"{key}={value!r}"))
    threshold = interval.get("threshold")
    if isinstance(threshold, (int, float)) and threshold > 1:
        findings.append(Finding(rel(path), "rho_threshold_public_bound_invalid", f"threshold={threshold!r}"))
    lower = interval.get("lower")
    mean = interval.get("mean")
    upper = interval.get("upper")
    if all(isinstance(v, (int, float)) for v in (lower, mean, upper)) and not lower <= mean <= upper:
        findings.append(Finding(rel(path), "rho_interval_order_invalid", "expected lower <= mean <= upper"))
    return findings


def validate_loss_bounds(path: Path, bounds: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(bounds, dict):
        return [Finding(rel(path), "loss_bounds_invalid", "must be object")]
    required = {"aar_99_upper", "aes_99_upper", "max_allowed_aar_99", "max_allowed_aes_99"}
    findings.extend(require_keys(path, bounds, required))
    for key in required:
        value = bounds.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            findings.append(Finding(rel(path), "loss_bound_invalid", f"{key}={value!r}"))
    return findings


def validate_fastgate(path: Path, fastgate: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(fastgate, dict):
        return [Finding(rel(path), "fastgate_invalid", "must be object")]

    mode = fastgate.get("mode")
    if mode not in FASTGATE_MODES:
        findings.append(Finding(rel(path), "fastgate_mode_invalid", str(mode)))

    method = fastgate.get("positive_vector_method")
    if method is not None and method not in FASTGATE_POSITIVE_VECTOR_METHODS:
        findings.append(Finding(rel(path), "fastgate_positive_vector_method_invalid", str(method)))

    upper_bound = fastgate.get("upper_bound")
    if upper_bound is not None and (not isinstance(upper_bound, (int, float)) or upper_bound < 0):
        findings.append(Finding(rel(path), "fastgate_upper_bound_invalid", str(upper_bound)))

    if mode == "perron_collatz_bound":
        if method is None:
            findings.append(Finding(rel(path), "fastgate_positive_vector_method_missing", "perron_collatz_bound requires positive_vector_method"))
        if upper_bound is None:
            findings.append(Finding(rel(path), "fastgate_upper_bound_missing", "perron_collatz_bound requires upper_bound"))

    return findings


def validate_evidence(path: Path, evidence: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(evidence, dict):
        return [Finding(rel(path), "evidence_invalid", "must be object")]
    findings.extend(require_keys(path, evidence, {"source_type", "source_id", "synthetic"}))
    if evidence.get("source_type") not in EVIDENCE_SOURCE_TYPES:
        findings.append(Finding(rel(path), "evidence_source_type_invalid", str(evidence.get("source_type"))))
    if evidence.get("synthetic") is not True:
        findings.append(Finding(rel(path), "example_not_synthetic", "public examples must be synthetic"))
    evidence_hash = evidence.get("evidence_hash")
    if evidence_hash is not None and not SHA256_RE.match(str(evidence_hash)):
        findings.append(Finding(rel(path), "evidence_hash_invalid", str(evidence_hash)))
    return findings


def validate_calibration_profile(path: Path, obj: dict[str, Any], registered: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    required = {"profile_id", "risk_model_version", "level", "decision_horizon", "source", "evidence_window", "confidence", "uncertainty", "edge_weight_policy", "certification_status", "caveats"}
    findings.extend(require_keys(path, obj, required))
    if not CAL_PROFILE_RE.match(str(obj.get("profile_id"))):
        findings.append(Finding(rel(path), "profile_id_invalid", str(obj.get("profile_id"))))
    if not RISK_MODEL_RE.match(str(obj.get("risk_model_version"))):
        findings.append(Finding(rel(path), "risk_model_version_invalid", str(obj.get("risk_model_version"))))
    if obj.get("level") not in LEVELS:
        findings.append(Finding(rel(path), "calibration_level_invalid", str(obj.get("level"))))
    if obj.get("level") == "A0" and obj.get("certification_status") != "non_certifiable":
        findings.append(Finding(rel(path), "a0_must_be_non_certifiable", str(obj.get("certification_status"))))
    findings.extend(validate_horizon(path, obj.get("decision_horizon")))
    findings.extend(validate_evidence_window(path, obj.get("evidence_window")))
    findings.extend(validate_rho_interval(path, {
        "lower": obj.get("uncertainty", {}).get("rho_lower") if isinstance(obj.get("uncertainty"), dict) else None,
        "mean": obj.get("uncertainty", {}).get("rho_mean") if isinstance(obj.get("uncertainty"), dict) else None,
        "upper": obj.get("uncertainty", {}).get("rho_upper") if isinstance(obj.get("uncertainty"), dict) else None,
        "threshold": obj.get("uncertainty", {}).get("rho_upper") if isinstance(obj.get("uncertainty"), dict) else None
    }))
    return findings


def validate_context(path: Path, obj: dict[str, Any], registered: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    required = {"risk_model_version", "calibration_profile_id", "calibration_level", "decision_horizon", "graph_hash", "rho_interval", "decision", "reason_codes", "evidence", "autonomy_budget"}
    findings.extend(require_keys(path, obj, required))
    if not RISK_MODEL_RE.match(str(obj.get("risk_model_version"))):
        findings.append(Finding(rel(path), "risk_model_version_invalid", str(obj.get("risk_model_version"))))
    if not CAL_PROFILE_RE.match(str(obj.get("calibration_profile_id"))):
        findings.append(Finding(rel(path), "profile_id_invalid", str(obj.get("calibration_profile_id"))))
    if obj.get("calibration_level") not in LEVELS:
        findings.append(Finding(rel(path), "calibration_level_invalid", str(obj.get("calibration_level"))))
    if not SHA256_RE.match(str(obj.get("graph_hash"))):
        findings.append(Finding(rel(path), "graph_hash_invalid", str(obj.get("graph_hash"))))
    if obj.get("decision") not in VERDICTS:
        findings.append(Finding(rel(path), "verdict_invalid", str(obj.get("decision"))))
    findings.extend(validate_horizon(path, obj.get("decision_horizon")))
    findings.extend(validate_rho_interval(path, obj.get("rho_interval")))
    if "loss_bounds" in obj:
        findings.extend(validate_loss_bounds(path, obj.get("loss_bounds")))
    if "fastgate" in obj:
        findings.extend(validate_fastgate(path, obj.get("fastgate")))
    findings.extend(validate_reason_codes(path, obj.get("reason_codes"), registered))
    findings.extend(validate_evidence(path, obj.get("evidence")))
    return findings


def validate_certificate(path: Path, obj: dict[str, Any], registered: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    required = {"certificate_id", "certificate_type", "risk_model_version", "calibration_profile", "decision_horizon", "graph_hash", "verdict", "rho_interval", "loss_bounds", "evidence", "reason_codes", "issued_at", "caveats"}
    findings.extend(require_keys(path, obj, required))
    if not CERT_ID_RE.match(str(obj.get("certificate_id"))):
        findings.append(Finding(rel(path), "certificate_id_invalid", str(obj.get("certificate_id"))))
    if not RISK_MODEL_RE.match(str(obj.get("risk_model_version"))):
        findings.append(Finding(rel(path), "risk_model_version_invalid", str(obj.get("risk_model_version"))))
    if not SHA256_RE.match(str(obj.get("graph_hash"))):
        findings.append(Finding(rel(path), "graph_hash_invalid", str(obj.get("graph_hash"))))
    if obj.get("verdict") not in VERDICTS:
        findings.append(Finding(rel(path), "verdict_invalid", str(obj.get("verdict"))))
    findings.extend(validate_horizon(path, obj.get("decision_horizon")))
    findings.extend(validate_rho_interval(path, obj.get("rho_interval")))
    findings.extend(validate_loss_bounds(path, obj.get("loss_bounds")))
    if "fastgate" in obj:
        findings.extend(validate_fastgate(path, obj.get("fastgate")))
    findings.extend(validate_reason_codes(path, obj.get("reason_codes"), registered))
    findings.extend(validate_evidence(path, obj.get("evidence")))
    profile = obj.get("calibration_profile")
    if not isinstance(profile, dict):
        findings.append(Finding(rel(path), "calibration_profile_invalid", "must be object"))
    elif profile.get("level") == "A0":
        if profile.get("certification_status") != "non_certifiable":
            findings.append(Finding(rel(path), "a0_must_be_non_certifiable", str(profile.get("certification_status"))))
        if "ARCANA_INFO_A0_NON_CERTIFIABLE" not in obj.get("reason_codes", []):
            findings.append(Finding(rel(path), "a0_missing_info_reason", "ARCANA_INFO_A0_NON_CERTIFIABLE required"))
    return findings


def validate_benchmark(path: Path, obj: dict[str, Any], registered: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    required = {"scenario_id", "title", "summary", "synthetic", "scenario_type", "threat_class", "calibration_level", "initial_rho_upper", "graph_fixture", "expected_arcana_response", "reported_metrics"}
    findings.extend(require_keys(path, obj, required))
    if not SCENARIO_ID_RE.match(str(obj.get("scenario_id"))):
        findings.append(Finding(rel(path), "scenario_id_invalid", str(obj.get("scenario_id"))))
    if obj.get("synthetic") is not True:
        findings.append(Finding(rel(path), "example_not_synthetic", "benchmark examples must be synthetic"))
    scenario_type = obj.get("scenario_type")
    if scenario_type not in BENCHMARK_SCENARIO_TYPES:
        findings.append(Finding(rel(path), "benchmark_scenario_type_invalid", str(scenario_type)))
    negative_control = obj.get("negative_control")
    if scenario_type == "negative_control":
        if negative_control not in BENCHMARK_NEGATIVE_CONTROLS:
            findings.append(Finding(rel(path), "benchmark_negative_control_invalid", str(negative_control)))
    elif negative_control is not None:
        findings.append(Finding(rel(path), "benchmark_negative_control_unexpected", str(negative_control)))
    graph = obj.get("graph_fixture")
    if isinstance(graph, dict):
        if not SHA256_RE.match(str(graph.get("graph_hash"))):
            findings.append(Finding(rel(path), "graph_hash_invalid", str(graph.get("graph_hash"))))
    else:
        findings.append(Finding(rel(path), "graph_fixture_invalid", "must be object"))
    response = obj.get("expected_arcana_response")
    if isinstance(response, dict):
        if response.get("verdict") not in VERDICTS:
            findings.append(Finding(rel(path), "verdict_invalid", str(response.get("verdict"))))
        findings.extend(validate_reason_codes(path, response.get("reason_codes"), registered))
    else:
        findings.append(Finding(rel(path), "expected_response_invalid", "must be object"))
    return findings


def validate_benchmark_execution_suite(path: Path, obj: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(require_keys(path, obj, {"suite_id", "synthetic", "evaluator_api", "cases"}))
    if not SCENARIO_ID_RE.match(str(obj.get("suite_id"))):
        findings.append(Finding(rel(path), "benchmark_suite_id_invalid", str(obj.get("suite_id"))))
    if obj.get("synthetic") is not True:
        findings.append(Finding(rel(path), "benchmark_suite_not_synthetic", "public execution suite must be synthetic"))
    if obj.get("evaluator_api") != "arcana.decision.evaluate_decision.v0.1":
        findings.append(Finding(rel(path), "benchmark_evaluator_api_invalid", str(obj.get("evaluator_api"))))
    cases = obj.get("cases")
    if not isinstance(cases, list) or not cases:
        return [*findings, Finding(rel(path), "benchmark_execution_cases_invalid", "cases must be a non-empty array")]
    scenario_ids: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            findings.append(Finding(rel(path), "benchmark_execution_case_invalid", f"cases[{index}] must be object"))
            continue
        scenario_id = case.get("scenario_id")
        if not SCENARIO_ID_RE.match(str(scenario_id)):
            findings.append(Finding(rel(path), "scenario_id_invalid", f"cases[{index}].scenario_id={scenario_id!r}"))
        else:
            scenario_ids.append(str(scenario_id))
    if len(scenario_ids) != len(set(scenario_ids)):
        findings.append(Finding(rel(path), "benchmark_execution_scenario_id_duplicate", "case scenario_id values must be unique"))
    if scenario_ids != sorted(scenario_ids):
        findings.append(Finding(rel(path), "benchmark_execution_case_order_invalid", "cases must be sorted by scenario_id"))
    return findings


def validate_example(path: Path, registered: set[str]) -> list[Finding]:
    obj = load_json(path)
    if not isinstance(obj, dict):
        return [Finding(rel(path), "example_not_object", "top-level JSON must be object")]
    schema_version = obj.get("schema_version")
    if schema_version == "arcana.calibration_profile.v0.2":
        return validate_calibration_profile(path, obj, registered)
    if schema_version == "arcana.context.v0.2":
        return validate_context(path, obj, registered)
    if schema_version == "arcana.certificate.v0.2":
        return validate_certificate(path, obj, registered)
    if schema_version == "arcana.benchmark_scenario.v0.2":
        return validate_benchmark(path, obj, registered)
    if schema_version == "arcana.benchmark_execution_suite.v0.1":
        return validate_benchmark_execution_suite(path, obj)
    return [Finding(rel(path), "unknown_example_schema_version", str(schema_version))]


def main() -> int:
    findings: list[Finding] = []
    registered = load_registered_reason_codes()
    schemas_by_version: dict[str, dict[str, Any]] = {}

    for schema_path in sorted(SCHEMA_DIR.glob("*.json")):
        schema = load_json(schema_path)
        if not isinstance(schema, dict):
            findings.append(Finding(rel(schema_path), "schema_not_object", "top-level schema must be object"))
            continue
        findings.extend(check_schema_file(schema_path, schema))
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            findings.append(Finding(rel(schema_path), "jsonschema_meta_validation_failed", exc.message))
        version = schema.get("properties", {}).get("schema_version", {}).get("const")
        if isinstance(version, str):
            schemas_by_version[version] = schema

    for expected_schema in SCHEMAS.values():
        if not (SCHEMA_DIR / expected_schema).exists():
            findings.append(Finding(rel(SCHEMA_DIR / expected_schema), "schema_missing", expected_schema))

    for example_path in sorted(EXAMPLE_DIR.glob("*.json")):
        example = load_json(example_path)
        version = example.get("schema_version") if isinstance(example, dict) else None
        schema = schemas_by_version.get(version) if isinstance(version, str) else None
        if schema is None:
            findings.append(Finding(rel(example_path), "example_schema_unavailable", str(version)))
        else:
            validator = Draft202012Validator(schema, format_checker=FormatChecker())
            for error in sorted(validator.iter_errors(example), key=lambda item: (tuple(item.absolute_path), tuple(item.absolute_schema_path))):
                location = ".".join(str(part) for part in error.absolute_path) or "$"
                findings.append(Finding(rel(example_path), f"jsonschema_{error.validator}", f"{location}: {error.message}"))
        findings.extend(validate_example(example_path, registered))

    if findings:
        print("schema validation: FAIL")
        for finding in findings:
            print(f"- {finding.path} [{finding.code}] {finding.detail}")
        return 1

    print("schema validation: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
