"""Deterministic ARCANA-Bench execution, reporting, and verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from arcana._resources import provenance_path
from arcana._validation import fail, issue
from arcana.bench import BENCHMARK_SCENARIO_GLOB, BenchmarkSuite, load_public_benchmark_suite
from arcana.benchmark_input import (
    BENCHMARK_EVALUATOR_API,
    BenchmarkEvaluatorInput,
    BenchmarkExecutionCase,
    BenchmarkExecutionSuite,
    canonical_json_bytes,
    sha256_json,
)
from arcana.decision import DecisionEvaluationRequest, evaluate_decision
from arcana.errors import (
    ArcanaValidationError,
    CalibrationLevel,
    FastGateMode,
    ReasonCode,
    Verdict,
)
from arcana.model import BenchmarkScenario, DecisionHorizon, DecisionResult
from arcana.schemas import EXAMPLE_DIR, ROOT, SCHEMA_DIR, load_json, load_typed_fixture


BENCHMARK_EXECUTION_SUITE_FILENAME = "arcana_bench_execution_suite.synthetic.json"
BENCHMARK_RUN_REPORT_SCHEMA_FILENAME = "ARCANA_BenchmarkRunReport.schema.v0.1.json"
BENCHMARK_RUN_REPORT_SCHEMA_VERSION = "arcana.benchmark_run_report.v0.1"
BENCHMARK_RUNNER_VERSION = "arcana.bench.runner.v0.1"
BENCHMARK_RUN_REPORT_ID = "arcana-bench-v0.1-synthetic-run"
BENCHMARK_CLAIM_BOUNDARY = "synthetic_reference_evaluator_only_not_empirical_system_benchmark"
BENCHMARK_METRIC_DECIMAL_PLACES = 12
BENCHMARK_NUMERIC_REPORTING_POLICY = "round_half_even_12_decimal_places_after_decision"

_CALIBRATION_RANK = {
    CalibrationLevel.A0: 0,
    CalibrationLevel.A1: 1,
    CalibrationLevel.A2: 2,
    CalibrationLevel.A3: 3,
}

_STATIC_PROVENANCE_PATHS = (
    "examples/arcana_bench_execution_suite.synthetic.json",
    "pyproject.toml",
    "schemas/ARCANA_BenchmarkExecutionSuite.schema.v0.1.json",
    "schemas/ARCANA_BenchmarkRunReport.schema.v0.1.json",
    "schemas/ARCANA_BenchmarkScenario.schema.v0.2.json",
    "src/arcana/__init__.py",
    "src/arcana/_numerics.py",
    "src/arcana/_resources.py",
    "src/arcana/_validation.py",
    "src/arcana/artifacts.py",
    "src/arcana/bench.py",
    "src/arcana/bench_runner.py",
    "src/arcana/benchmark_input.py",
    "src/arcana/calibration.py",
    "src/arcana/certificate.py",
    "src/arcana/decision.py",
    "src/arcana/demo.py",
    "src/arcana/errors.py",
    "src/arcana/fastgate.py",
    "src/arcana/loss.py",
    "src/arcana/matrices.py",
    "src/arcana/model.py",
    "src/arcana/schemas.py",
)


@dataclass(frozen=True)
class InputManifestEntry:
    path: str
    sha256: str

    def to_mapping(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256}


@dataclass(frozen=True)
class DecisionSnapshot:
    verdict: str
    reason_codes: tuple[str, ...]
    required_controls: tuple[str, ...]
    issue_code: str | None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reason_codes": list(self.reason_codes),
            "required_controls": list(self.required_controls),
            "issue_code": self.issue_code,
        }


@dataclass(frozen=True)
class MetricResult:
    name: str
    status: str
    value: float | None
    provenance: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "value": self.value,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class ScenarioRun:
    scenario_id: str
    input_hash: str
    expected: DecisionSnapshot
    observed: DecisionSnapshot
    verdict_comparison: str
    reason_codes_comparison: str
    required_controls_comparison: str
    metrics: tuple[MetricResult, ...]
    passed: bool

    def to_mapping(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "input_hash": self.input_hash,
            "expected": self.expected.to_mapping(),
            "observed": self.observed.to_mapping(),
            "comparisons": {
                "verdict": self.verdict_comparison,
                "reason_codes": self.reason_codes_comparison,
                "required_controls": self.required_controls_comparison,
            },
            "metrics": [metric.to_mapping() for metric in self.metrics],
            "passed": self.passed,
        }


@dataclass(frozen=True)
class BenchmarkRunReport:
    suite_id: str
    input_manifest: tuple[InputManifestEntry, ...]
    suite_input_hash: str
    scenarios: tuple[ScenarioRun, ...]
    report_hash: str

    @classmethod
    def create(
        cls,
        *,
        suite_id: str,
        input_manifest: tuple[InputManifestEntry, ...],
        scenarios: tuple[ScenarioRun, ...],
    ) -> "BenchmarkRunReport":
        draft = cls(
            suite_id=suite_id,
            input_manifest=input_manifest,
            suite_input_hash=_manifest_hash(input_manifest),
            scenarios=scenarios,
            report_hash="",
        )
        return replace(draft, report_hash=sha256_json(draft.body_mapping()))

    @property
    def passed_count(self) -> int:
        return sum(1 for scenario in self.scenarios if scenario.passed)

    @property
    def failed_count(self) -> int:
        return len(self.scenarios) - self.passed_count

    @property
    def execution_status(self) -> str:
        return "passed" if self.failed_count == 0 else "failed"

    def body_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": BENCHMARK_RUN_REPORT_SCHEMA_VERSION,
            "report_id": BENCHMARK_RUN_REPORT_ID,
            "runner_version": BENCHMARK_RUNNER_VERSION,
            "evaluator_api": BENCHMARK_EVALUATOR_API,
            "suite_id": self.suite_id,
            "synthetic": True,
            "claim_boundary": BENCHMARK_CLAIM_BOUNDARY,
            "numeric_reporting_policy": BENCHMARK_NUMERIC_REPORTING_POLICY,
            "input_manifest": [entry.to_mapping() for entry in self.input_manifest],
            "suite_input_hash": self.suite_input_hash,
            "execution_status": self.execution_status,
            "scenario_count": len(self.scenarios),
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "scenarios": [scenario.to_mapping() for scenario in self.scenarios],
        }

    def to_mapping(self) -> dict[str, Any]:
        return {**self.body_mapping(), "report_hash": self.report_hash}


def load_public_benchmark_execution_suite(example_dir: Path = EXAMPLE_DIR) -> BenchmarkExecutionSuite:
    path = example_dir / BENCHMARK_EXECUTION_SUITE_FILENAME
    loaded = load_typed_fixture(path)
    if not isinstance(loaded, BenchmarkExecutionSuite):
        fail(
            "benchmark_execution_fixture_type_invalid",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "benchmark execution fixture did not parse as BenchmarkExecutionSuite",
            (str(path),),
        )
    return loaded


def validate_execution_binding(
    benchmark_suite: BenchmarkSuite,
    execution_suite: BenchmarkExecutionSuite,
) -> tuple[tuple[BenchmarkScenario, BenchmarkExecutionCase], ...]:
    scenario_by_id = {scenario.scenario_id: scenario for scenario in benchmark_suite.scenarios}
    case_by_id = {case.scenario_id: case for case in execution_suite.cases}
    missing_inputs = tuple(sorted(set(scenario_by_id) - set(case_by_id)))
    if missing_inputs:
        fail(
            "benchmark_execution_input_missing",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            f"execution input missing for scenario ids: {', '.join(missing_inputs)}",
            ("execution_suite", "cases"),
        )
    extra_inputs = tuple(sorted(set(case_by_id) - set(scenario_by_id)))
    if extra_inputs:
        fail(
            "benchmark_execution_input_unbound",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            f"execution input has no scenario contract: {', '.join(extra_inputs)}",
            ("execution_suite", "cases"),
        )
    bindings = tuple(
        (scenario_by_id[scenario_id], case_by_id[scenario_id])
        for scenario_id in sorted(scenario_by_id)
    )
    for scenario, case in bindings:
        _validate_case_binding(scenario, case)
    return bindings


def execute_benchmark_suite(
    benchmark_suite: BenchmarkSuite,
    execution_suite: BenchmarkExecutionSuite,
    input_manifest: tuple[InputManifestEntry, ...],
    *,
    evaluator: Callable[[DecisionEvaluationRequest], DecisionResult] = evaluate_decision,
) -> BenchmarkRunReport:
    if not callable(evaluator):
        fail(
            "benchmark_evaluator_not_callable",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "evaluator must be callable",
            ("evaluator",),
        )
    bindings = validate_execution_binding(benchmark_suite, execution_suite)
    runs: list[ScenarioRun] = []
    for scenario, case in bindings:
        observed = evaluator(case.evaluator_input.to_decision_request())
        if not isinstance(observed, DecisionResult):
            fail(
                "benchmark_evaluator_result_invalid",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "evaluator must return DecisionResult",
                ("scenarios", scenario.scenario_id, "observed"),
            )
        runs.append(_scenario_run(scenario, case, observed))
    report = BenchmarkRunReport.create(
        suite_id=execution_suite.suite_id,
        input_manifest=input_manifest,
        scenarios=tuple(runs),
    )
    verify_benchmark_report(report.to_mapping())
    return report


def run_public_benchmark(root: Path = ROOT) -> BenchmarkRunReport:
    example_dir = root / "examples"
    benchmark_suite = load_public_benchmark_suite(example_dir)
    execution_suite = load_public_benchmark_execution_suite(example_dir)
    manifest = build_input_manifest(root)
    return execute_benchmark_suite(benchmark_suite, execution_suite, manifest)


def build_input_manifest(root: Path = ROOT) -> tuple[InputManifestEntry, ...]:
    scenario_paths = tuple(
        path.relative_to(root).as_posix()
        for path in sorted((root / "examples").glob(BENCHMARK_SCENARIO_GLOB))
    )
    relative_paths = tuple(sorted({*_STATIC_PROVENANCE_PATHS, *scenario_paths}))
    entries: list[InputManifestEntry] = []
    for relative_path in relative_paths:
        path = provenance_path(root, relative_path)
        if path.is_symlink():
            fail(
                "benchmark_input_manifest_symlink_rejected",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "benchmark provenance inputs must not be symbolic links",
                ("input_manifest", relative_path),
            )
        if not path.exists():
            fail(
                "benchmark_input_manifest_file_missing",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "benchmark provenance input file is missing",
                ("input_manifest", relative_path),
            )
        if not path.is_file():
            fail(
                "benchmark_input_manifest_not_regular_file",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "benchmark provenance input must be a regular file",
                ("input_manifest", relative_path),
            )
        try:
            payload = path.read_bytes()
        except PermissionError as exc:
            raise ArcanaValidationError(
                issue(
                    "benchmark_input_manifest_permission_denied",
                    ReasonCode.DENY_MODEL_INPUT_INVALID,
                    "benchmark provenance input is not readable",
                    ("input_manifest", relative_path),
                )
            ) from exc
        except OSError as exc:
            raise ArcanaValidationError(
                issue(
                    "benchmark_input_manifest_read_failed",
                    ReasonCode.DENY_MODEL_INPUT_INVALID,
                    f"benchmark provenance input read failed: {exc}",
                    ("input_manifest", relative_path),
                )
            ) from exc
        entries.append(
            InputManifestEntry(
                path=relative_path,
                sha256=f"sha256:{hashlib.sha256(payload).hexdigest()}",
            )
        )
    return tuple(entries)


def report_json_bytes(report: BenchmarkRunReport) -> bytes:
    try:
        rendered = json.dumps(
            report.to_mapping(),
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ArcanaValidationError(
            issue(
                "benchmark_report_json_invalid",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                f"benchmark report cannot be encoded as JSON: {exc}",
                ("report",),
            )
        ) from exc
    return f"{rendered}\n".encode("ascii")


def verify_benchmark_report(document: Mapping[str, Any]) -> None:
    _validate_report_schema(document)
    input_manifest = document["input_manifest"]
    manifest_paths = tuple(entry["path"] for entry in input_manifest)
    if manifest_paths != tuple(sorted(manifest_paths)):
        fail(
            "benchmark_report_manifest_order_invalid",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "input_manifest must be sorted by path",
            ("input_manifest",),
        )
    if len(manifest_paths) != len(set(manifest_paths)):
        fail(
            "benchmark_report_manifest_path_duplicate",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "input_manifest paths must be unique",
            ("input_manifest",),
        )
    expected_suite_hash = sha256_json(input_manifest)
    if document["suite_input_hash"] != expected_suite_hash:
        fail(
            "benchmark_report_suite_input_hash_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "suite_input_hash does not match input_manifest",
            ("suite_input_hash",),
        )
    scenarios = document["scenarios"]
    scenario_ids = tuple(item["scenario_id"] for item in scenarios)
    if scenario_ids != tuple(sorted(scenario_ids)):
        fail(
            "benchmark_report_scenario_order_invalid",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "report scenarios must be sorted by scenario_id",
            ("scenarios",),
        )
    if len(scenario_ids) != len(set(scenario_ids)):
        fail(
            "benchmark_report_scenario_id_duplicate",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "report scenario ids must be unique",
            ("scenarios",),
        )
    passed_count = sum(1 for item in scenarios if item["passed"])
    failed_count = len(scenarios) - passed_count
    if document["scenario_count"] != len(scenarios):
        fail(
            "benchmark_report_scenario_count_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "scenario_count does not match scenarios",
            ("scenario_count",),
        )
    if document["passed_count"] != passed_count:
        fail(
            "benchmark_report_passed_count_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "passed_count does not match scenarios",
            ("passed_count",),
        )
    if document["failed_count"] != failed_count:
        fail(
            "benchmark_report_failed_count_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "failed_count does not match scenarios",
            ("failed_count",),
        )
    expected_status = "passed" if failed_count == 0 else "failed"
    if document["execution_status"] != expected_status:
        fail(
            "benchmark_report_execution_status_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "execution_status does not match scenario comparison results",
            ("execution_status",),
        )
    for index, scenario in enumerate(scenarios):
        expected = scenario["expected"]
        observed = scenario["observed"]
        comparisons = scenario["comparisons"]
        if expected["issue_code"] is not None:
            fail(
                "benchmark_report_expected_issue_code_unexpected",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "expected fixture snapshots do not declare evaluator issue_code values",
                ("scenarios", index, "expected", "issue_code"),
            )
        derived_comparisons = {
            "verdict": "pass" if expected["verdict"] == observed["verdict"] else "fail",
            "reason_codes": "pass" if expected["reason_codes"] == observed["reason_codes"] else "fail",
            "required_controls": "pass"
            if expected["required_controls"] == observed["required_controls"]
            else "fail",
        }
        comparison_checks = (
            ("verdict", "benchmark_report_verdict_comparison_mismatch"),
            ("reason_codes", "benchmark_report_reason_codes_comparison_mismatch"),
            ("required_controls", "benchmark_report_required_controls_comparison_mismatch"),
        )
        for field_name, code in comparison_checks:
            if comparisons[field_name] != derived_comparisons[field_name]:
                fail(
                    code,
                    ReasonCode.DENY_MODEL_INPUT_INVALID,
                    f"{field_name} comparison does not match expected and observed values",
                    ("scenarios", index, "comparisons", field_name),
                )
        metric_names = tuple(metric["name"] for metric in scenario["metrics"])
        if len(metric_names) != len(set(metric_names)):
            fail(
                "benchmark_report_metric_name_duplicate",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "scenario metric names must be unique",
                ("scenarios", index, "metrics"),
            )
        comparison_passed = all(value == "pass" for value in scenario["comparisons"].values())
        if scenario["passed"] is not comparison_passed:
            fail(
                "benchmark_report_scenario_pass_status_mismatch",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "scenario passed flag does not match comparisons",
                ("scenarios", index, "passed"),
            )
    body = dict(document)
    report_hash = body.pop("report_hash")
    expected_report_hash = sha256_json(body)
    if report_hash != expected_report_hash:
        fail(
            "benchmark_report_hash_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "report_hash does not match canonical report content",
            ("report_hash",),
        )


def verify_benchmark_report_against_source(
    document: Mapping[str, Any],
    root: Path = ROOT,
) -> None:
    verify_benchmark_report(document)
    current_manifest = [entry.to_mapping() for entry in build_input_manifest(root)]
    if document["input_manifest"] != current_manifest:
        fail(
            "benchmark_report_source_manifest_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "report input_manifest does not match the current benchmark source files",
            ("input_manifest",),
        )
    benchmark_suite = load_public_benchmark_suite(root / "examples")
    execution_suite = load_public_benchmark_execution_suite(root / "examples")
    reproduced = execute_benchmark_suite(
        benchmark_suite,
        execution_suite,
        build_input_manifest(root),
    ).to_mapping()
    if document["suite_id"] != reproduced["suite_id"]:
        fail(
            "benchmark_report_source_suite_id_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "report suite_id does not match the current execution suite",
            ("suite_id",),
        )
    report_scenarios = document["scenarios"]
    reproduced_scenarios = reproduced["scenarios"]
    report_ids = tuple(item["scenario_id"] for item in report_scenarios)
    reproduced_ids = tuple(item["scenario_id"] for item in reproduced_scenarios)
    if report_ids != reproduced_ids:
        fail(
            "benchmark_report_source_scenario_set_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "report scenario set does not match current benchmark source",
            ("scenarios",),
        )
    source_field_checks = (
        ("input_hash", "benchmark_report_source_input_hash_mismatch", "scenario input hash differs from current source"),
        ("expected", "benchmark_report_source_expected_mismatch", "expected decision differs from current scenario contract"),
        ("observed", "benchmark_report_source_observed_mismatch", "observed decision differs from current evaluator output"),
        ("comparisons", "benchmark_report_source_comparisons_mismatch", "comparisons differ from current evaluator output"),
        ("metrics", "benchmark_report_source_metrics_mismatch", "metric results differ from current evaluator output"),
        ("passed", "benchmark_report_source_pass_status_mismatch", "pass status differs from current evaluator output"),
    )
    for index, (reported, expected) in enumerate(zip(report_scenarios, reproduced_scenarios, strict=True)):
        for field_name, code, detail in source_field_checks:
            if reported[field_name] != expected[field_name]:
                fail(
                    code,
                    ReasonCode.DENY_MODEL_INPUT_INVALID,
                    detail,
                    ("scenarios", index, field_name),
                )
    if document != reproduced:
        fail(
            "benchmark_report_source_reproduction_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "report differs from deterministic execution against current source",
            ("report",),
        )


def _validate_case_binding(scenario: BenchmarkScenario, case: BenchmarkExecutionCase) -> None:
    evaluator_input = case.evaluator_input
    matrix = evaluator_input.matrix_interval
    profile = evaluator_input.calibration_profile
    if scenario.calibration_level is not profile.level:
        fail(
            "benchmark_execution_calibration_level_mismatch",
            ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            "scenario calibration_level must match evaluator profile level",
            ("execution_suite", case.scenario_id, "calibration_profile", "level"),
        )
    if evaluator_input.risk_model_version != profile.risk_model_version:
        fail(
            "benchmark_execution_profile_model_mismatch",
            ReasonCode.DENY_RISK_MODEL_UNSUPPORTED,
            "calibration profile model must match evaluator request model",
            ("execution_suite", case.scenario_id, "calibration_profile", "risk_model_version"),
        )
    if evaluator_input.risk_model_version not in evaluator_input.supported_risk_model_versions:
        fail(
            "benchmark_execution_model_not_supported",
            ReasonCode.DENY_RISK_MODEL_UNSUPPORTED,
            "request model must appear in supported_risk_model_versions",
            ("execution_suite", case.scenario_id, "supported_risk_model_versions"),
        )
    if evaluator_input.request_graph_hash != scenario.graph_fixture.graph_hash:
        fail(
            "benchmark_execution_scenario_graph_mismatch",
            ReasonCode.DENY_GRAPH_HASH_MISMATCH,
            "request graph hash must bind to the scenario graph fixture",
            ("execution_suite", case.scenario_id, "request_graph_hash"),
        )
    if matrix.dimension != scenario.graph_fixture.node_count:
        fail(
            "benchmark_execution_node_count_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "matrix dimension must match scenario node_count",
            ("execution_suite", case.scenario_id, "matrix_interval", "dimension"),
        )
    if matrix.edge_count != scenario.graph_fixture.edge_count:
        fail(
            "benchmark_execution_edge_count_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "matrix edge_count must match scenario edge_count",
            ("execution_suite", case.scenario_id, "matrix_interval", "edge_count"),
        )
    if not _close(matrix.rho_upper_target, scenario.initial_rho_upper):
        fail(
            "benchmark_execution_initial_rho_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "matrix rho_upper_target must match scenario initial_rho_upper",
            ("execution_suite", case.scenario_id, "matrix_interval", "rho_upper_target"),
        )
    uncertainty = profile.uncertainty
    target_pairs = (
        (uncertainty.rho_lower, matrix.rho_lower_target, "rho_lower"),
        (uncertainty.rho_mean, matrix.rho_mean_target, "rho_mean"),
        (uncertainty.rho_upper, matrix.rho_upper_target, "rho_upper"),
    )
    for profile_value, target_value, field_name in target_pairs:
        if not _close(profile_value, target_value):
            fail(
                "benchmark_execution_uncertainty_matrix_mismatch",
                ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
                "calibration uncertainty must match matrix rho targets",
                ("execution_suite", case.scenario_id, "calibration_profile", "uncertainty", field_name),
            )
    actual_rho = matrix.to_matrix_bundle().spectral_radii(evaluator_input.rho_threshold)
    actual_pairs = (
        (actual_rho.lower, matrix.rho_lower_target, "rho_lower_target"),
        (actual_rho.mean, matrix.rho_mean_target, "rho_mean_target"),
        (actual_rho.upper, matrix.rho_upper_target, "rho_upper_target"),
    )
    for actual_value, target_value, field_name in actual_pairs:
        if not _close(actual_value, target_value, absolute_tolerance=1e-10):
            fail(
                "benchmark_execution_constructed_rho_mismatch",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "constructed matrix spectral radius does not match declared target",
                ("execution_suite", case.scenario_id, "matrix_interval", field_name),
            )
    if scenario.negative_control == "missing_decision_horizon":
        if evaluator_input.decision_horizon is not None:
            fail(
                "benchmark_execution_missing_horizon_control_not_exercised",
                ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
                "missing_decision_horizon control requires a null request horizon",
                ("execution_suite", case.scenario_id, "decision_horizon"),
            )
    else:
        if evaluator_input.decision_horizon is None:
            fail(
                "benchmark_execution_horizon_missing_unexpected",
                ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
                "only missing_decision_horizon may use a null request horizon",
                ("execution_suite", case.scenario_id, "decision_horizon"),
            )
        if not _same_horizon(evaluator_input.decision_horizon, profile.decision_horizon):
            fail(
                "benchmark_execution_profile_horizon_mismatch",
                ReasonCode.DENY_DECISION_HORIZON_MISMATCH,
                "request horizon must match calibration profile horizon",
                ("execution_suite", case.scenario_id, "decision_horizon"),
            )
    if scenario.negative_control == "graph_hash_mismatch":
        if matrix.matrix_graph_hash == evaluator_input.request_graph_hash:
            fail(
                "benchmark_execution_graph_mismatch_control_not_exercised",
                ReasonCode.DENY_GRAPH_HASH_MISMATCH,
                "graph_hash_mismatch control requires distinct matrix and request hashes",
                ("execution_suite", case.scenario_id, "matrix_interval", "matrix_graph_hash"),
            )
    elif matrix.matrix_graph_hash != evaluator_input.request_graph_hash:
        fail(
            "benchmark_execution_matrix_graph_mismatch_unexpected",
            ReasonCode.DENY_GRAPH_HASH_MISMATCH,
            "only graph_hash_mismatch may use distinct matrix and request hashes",
            ("execution_suite", case.scenario_id, "matrix_interval", "matrix_graph_hash"),
        )
    if scenario.scenario_type == "negative_control":
        _validate_negative_control_input(scenario, evaluator_input)
    elif scenario.scenario_type == "coverage_scenario":
        _validate_coverage_input(scenario, evaluator_input)
    else:
        fail(
            "benchmark_execution_scenario_type_unsupported",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "unsupported scenario_type in execution binding",
            ("execution_suite", case.scenario_id),
        )


def _validate_negative_control_input(
    scenario: BenchmarkScenario,
    evaluator_input: BenchmarkEvaluatorInput,
) -> None:
    control = scenario.negative_control
    if control == "missing_decision_horizon":
        if evaluator_input.decision_horizon is not None:
            _negative_control_not_exercised(scenario, "request horizon must be null")
    elif control == "graph_hash_mismatch":
        if evaluator_input.matrix_interval.matrix_graph_hash == evaluator_input.request_graph_hash:
            _negative_control_not_exercised(scenario, "matrix and request graph hashes must differ")
    elif control == "a0_artifact_used_for_admission":
        if evaluator_input.calibration_profile.level is not CalibrationLevel.A0:
            _negative_control_not_exercised(scenario, "calibration profile must be A0")
        if _CALIBRATION_RANK[evaluator_input.required_calibration_level] < _CALIBRATION_RANK[CalibrationLevel.A1]:
            _negative_control_not_exercised(scenario, "required calibration must be A1 or stronger")
    elif control == "rho_mean_below_threshold_rho_upper_above_threshold":
        matrix = evaluator_input.matrix_interval
        if not matrix.rho_mean_target < evaluator_input.rho_threshold:
            _negative_control_not_exercised(scenario, "rho mean must be below threshold")
        if evaluator_input.tolerance_policy.below_threshold_with_margin(
            matrix.rho_upper_target,
            evaluator_input.rho_threshold,
        ):
            _negative_control_not_exercised(scenario, "rho upper must fail the threshold margin")
    elif control == "fastgate_inconclusive":
        fastgate = evaluator_input.fastgate
        if not evaluator_input.fastgate_required or fastgate is None:
            _negative_control_not_exercised(scenario, "FastGate must be required and present")
        if fastgate.mode is not FastGateMode.PERRON_COLLATZ_BOUND:
            _negative_control_not_exercised(scenario, "FastGate must use perron_collatz_bound")
        if fastgate.upper_bound is None:
            _negative_control_not_exercised(scenario, "FastGate upper bound must be present")
        if evaluator_input.tolerance_policy.below_threshold_with_margin(
            fastgate.upper_bound,
            evaluator_input.rho_threshold,
        ):
            _negative_control_not_exercised(scenario, "FastGate upper bound must fail the threshold margin")
    elif control == "loss_model_missing_required":
        if not evaluator_input.loss_in_scope or evaluator_input.loss_bounds is not None:
            _negative_control_not_exercised(scenario, "loss must be in scope with missing bounds")
    elif control == "stale_evidence":
        evidence = evaluator_input.calibration_profile.evidence_window
        decision_time = _parse_aware_datetime(evaluator_input.decision_time, (scenario.scenario_id, "decision_time"))
        observed_before = _parse_aware_datetime(evidence.observed_before, (scenario.scenario_id, "evidence_window", "observed_before"))
        if (decision_time - observed_before).total_seconds() <= evidence.max_age_seconds:
            _negative_control_not_exercised(scenario, "evidence age must exceed max_age_seconds")
    else:
        fail(
            "benchmark_execution_negative_control_unsupported",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "unsupported benchmark negative control",
            ("execution_suite", scenario.scenario_id, "negative_control"),
        )


def _validate_coverage_input(
    scenario: BenchmarkScenario,
    evaluator_input: BenchmarkEvaluatorInput,
) -> None:
    threat_class = scenario.threat_class
    if threat_class == "indirect_prompt_injection":
        if not evaluator_input.human_gate_required:
            _coverage_path_not_exercised(scenario, "human_gate_required must be true")
    elif threat_class == "persistent_memory_poisoning":
        if not evaluator_input.human_gate_required or evaluator_input.requested_memory_writes < 1:
            _coverage_path_not_exercised(scenario, "memory write plus human gate must be requested")
    elif threat_class == "tool_misuse":
        if not evaluator_input.scope_reduction_required:
            _coverage_path_not_exercised(scenario, "scope_reduction_required must be true")
        if not evaluator_input.loss_in_scope or evaluator_input.loss_bounds is None:
            _coverage_path_not_exercised(scenario, "tool misuse path must carry valid loss bounds")
    elif threat_class == "unsafe_delegation_loop":
        if evaluator_input.tolerance_policy.below_threshold_with_margin(
            evaluator_input.matrix_interval.rho_upper_target,
            evaluator_input.rho_threshold,
        ):
            _coverage_path_not_exercised(scenario, "delegation rho upper must fail threshold margin")
        if evaluator_input.scope_reduction_available:
            _coverage_path_not_exercised(scenario, "delegation denial path must not declare scope reduction available")
    elif threat_class == "benchmark_gaming":
        if evaluator_input.calibration_profile.level is not CalibrationLevel.A0:
            _coverage_path_not_exercised(scenario, "benchmark gaming path must demonstrate A0 observe-only")
    elif threat_class == "dynamic_execution_abuse":
        if _CALIBRATION_RANK[evaluator_input.required_calibration_level] <= _CALIBRATION_RANK[evaluator_input.calibration_profile.level]:
            _coverage_path_not_exercised(scenario, "dynamic execution path must require stronger calibration")
    else:
        fail(
            "benchmark_execution_threat_class_unsupported",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "unsupported coverage threat class",
            ("execution_suite", scenario.scenario_id, "threat_class"),
        )


def _scenario_run(
    scenario: BenchmarkScenario,
    case: BenchmarkExecutionCase,
    observed: DecisionResult,
) -> ScenarioRun:
    expected_snapshot = _decision_snapshot(scenario.expected_response, include_issue_code=False)
    observed_snapshot = _decision_snapshot(observed, include_issue_code=True)
    verdict_comparison = "pass" if observed.verdict is scenario.expected_response.verdict else "fail"
    reason_codes_comparison = "pass" if observed.reason_codes == scenario.expected_response.reason_codes else "fail"
    required_controls_comparison = (
        "pass" if observed.required_controls == scenario.expected_response.required_controls else "fail"
    )
    passed = all(
        result == "pass"
        for result in (verdict_comparison, reason_codes_comparison, required_controls_comparison)
    )
    return ScenarioRun(
        scenario_id=scenario.scenario_id,
        input_hash=case.evaluator_input.input_hash,
        expected=expected_snapshot,
        observed=observed_snapshot,
        verdict_comparison=verdict_comparison,
        reason_codes_comparison=reason_codes_comparison,
        required_controls_comparison=required_controls_comparison,
        metrics=tuple(_metric_result(metric, observed.metrics) for metric in scenario.reported_metrics),
        passed=passed,
    )


def _decision_snapshot(result: DecisionResult, *, include_issue_code: bool) -> DecisionSnapshot:
    issue_code: str | None = None
    if include_issue_code:
        raw_issue_code = result.metrics.get("issue_code")
        if raw_issue_code is not None and (not isinstance(raw_issue_code, str) or not raw_issue_code):
            fail(
                "benchmark_observed_issue_code_invalid",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "observed issue_code must be a non-empty string when present",
                ("observed", "metrics", "issue_code"),
            )
        issue_code = raw_issue_code
    return DecisionSnapshot(
        verdict=result.verdict.value,
        reason_codes=tuple(code.value for code in result.reason_codes),
        required_controls=result.required_controls,
        issue_code=issue_code,
    )


def _metric_result(metric: str, observed_metrics: Mapping[str, Any]) -> MetricResult:
    if metric == "task_success_rate":
        return MetricResult(metric, "not_measured", None, "no_task_execution_in_reference_evaluator")
    if metric == "unsafe_action_rate":
        return MetricResult(metric, "not_measured", None, "no_action_execution_in_reference_evaluator")
    if metric == "policy_violation_rate":
        return MetricResult(metric, "not_measured", None, "no_policy_workload_execution_in_reference_evaluator")
    if metric == "delta_rho_upper":
        return _evaluator_metric(metric, "delta_rho_upper", observed_metrics)
    if metric == "rho_peak":
        return _evaluator_metric(metric, "rho_upper", observed_metrics)
    if metric == "AaR_99_upper":
        return _evaluator_metric(metric, "aar_99_upper", observed_metrics)
    if metric == "AES_99_upper":
        return _evaluator_metric(metric, "aes_99_upper", observed_metrics)
    if metric == "containment_time_steps":
        return MetricResult(metric, "not_measured", None, "no_temporal_containment_simulation")
    if metric == "autonomy_budget_consumed":
        return MetricResult(metric, "unavailable", None, "multi_axis_budget_has_no_scalar_consumption_metric")
    if metric == "human_intervention_efficiency":
        return MetricResult(metric, "not_measured", None, "no_human_intervention_workload_execution")
    if metric == "artifact_contract_validity_rate":
        return MetricResult(metric, "measured", 1.0, "scenario_schema_and_typed_contract_validation")
    fail(
        "benchmark_metric_unsupported_at_execution",
        ReasonCode.DENY_MODEL_INPUT_INVALID,
        f"unsupported benchmark metric {metric!r}",
        ("reported_metrics",),
    )


def _evaluator_metric(
    public_name: str,
    evaluator_name: str,
    observed_metrics: Mapping[str, Any],
) -> MetricResult:
    if evaluator_name not in observed_metrics:
        return MetricResult(
            public_name,
            "unavailable",
            None,
            f"evaluator_path_did_not_emit_{evaluator_name}",
        )
    raw_value = observed_metrics[evaluator_name]
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
        fail(
            "benchmark_observed_metric_not_numeric",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            f"observed evaluator metric {evaluator_name} must be numeric",
            ("observed", "metrics", evaluator_name),
        )
    value = float(raw_value)
    if not math.isfinite(value):
        fail(
            "benchmark_observed_metric_nonfinite",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            f"observed evaluator metric {evaluator_name} must be finite",
            ("observed", "metrics", evaluator_name),
        )
    canonical_value = round(value, BENCHMARK_METRIC_DECIMAL_PLACES)
    if canonical_value == 0:
        canonical_value = 0.0
    return MetricResult(
        public_name,
        "measured",
        canonical_value,
        (
            f"arcana.decision.evaluate_decision.metrics.{evaluator_name};"
            f"report_rounding={BENCHMARK_METRIC_DECIMAL_PLACES}_decimal_places"
        ),
    )


def _validate_report_schema(document: Mapping[str, Any]) -> None:
    schema = load_json(SCHEMA_DIR / BENCHMARK_RUN_REPORT_SCHEMA_FILENAME)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(document),
        key=lambda item: (tuple(item.absolute_path), tuple(item.absolute_schema_path)),
    )
    if errors:
        error = errors[0]
        path = tuple(error.absolute_path)
        fail(
            f"benchmark_report_schema_{error.validator}",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            error.message,
            path,
        )


def _manifest_hash(entries: Sequence[InputManifestEntry]) -> str:
    return sha256_json([entry.to_mapping() for entry in entries])


def _negative_control_not_exercised(scenario: BenchmarkScenario, detail: str) -> None:
    fail(
        "benchmark_execution_negative_control_not_exercised",
        ReasonCode.DENY_MODEL_INPUT_INVALID,
        detail,
        ("execution_suite", scenario.scenario_id, "negative_control"),
    )


def _coverage_path_not_exercised(scenario: BenchmarkScenario, detail: str) -> None:
    fail(
        "benchmark_execution_coverage_path_not_exercised",
        ReasonCode.DENY_MODEL_INPUT_INVALID,
        detail,
        ("execution_suite", scenario.scenario_id, "threat_class"),
    )


def _same_horizon(left: DecisionHorizon, right: DecisionHorizon) -> bool:
    return (
        left.id == right.id
        and left.duration_seconds == right.duration_seconds
        and left.context == right.context
    )


def _close(left: float, right: float, *, absolute_tolerance: float = 1e-12) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=absolute_tolerance)


def _parse_aware_datetime(value: str, path: tuple[str | int, ...]) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(
            "benchmark_execution_datetime_invalid",
            ReasonCode.DENY_CONTEXT_STALE,
            "benchmark datetime must be RFC3339-compatible",
            path,
        )
    if parsed.tzinfo is None:
        fail(
            "benchmark_execution_datetime_timezone_missing",
            ReasonCode.DENY_CONTEXT_STALE,
            "benchmark datetime must include timezone",
            path,
        )
    return parsed


def _write_report_atomic(path: Path, payload: bytes) -> None:
    parent = path.parent
    if not parent.exists():
        fail(
            "benchmark_report_output_parent_missing",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "report output parent directory does not exist",
            (str(path),),
        )
    if not parent.is_dir():
        fail(
            "benchmark_report_output_parent_not_directory",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "report output parent must be a directory",
            (str(path),),
        )
    if path.is_symlink():
        fail(
            "benchmark_report_output_symlink_rejected",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "report output must not be a symbolic link",
            (str(path),),
        )
    if path.exists() and not path.is_file():
        fail(
            "benchmark_report_output_not_regular_file",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "existing report output must be a regular file",
            (str(path),),
        )
    descriptor = -1
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=parent)
        temporary_path = Path(temporary_name)
        if os.name != "nt":
            os.fchmod(descriptor, 0o644)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        if os.name != "nt":
            directory_descriptor = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    except OSError as exc:
        cleanup_detail = ""
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                temporary_path = None
            except OSError as cleanup_exc:
                cleanup_detail = f"; temporary-file cleanup failed: {cleanup_exc}"
        raise ArcanaValidationError(
            issue(
                "benchmark_report_atomic_write_failed",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                f"atomic report write failed: {exc}{cleanup_detail}",
                (str(path),),
            )
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute or verify the public synthetic ARCANA-Bench suite.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--output", type=Path, help="Atomically write the deterministic run report to this path.")
    actions.add_argument("--verify", type=Path, help="Verify the schema, semantics, and content hash of an existing report.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.verify is not None:
            document = load_json(args.verify)
            verify_benchmark_report_against_source(document)
            sys.stdout.write(f"benchmark report verification: PASS {document['report_hash']}\n")
            return 0
        report = run_public_benchmark()
        payload = report_json_bytes(report)
        if args.output is None:
            sys.stdout.buffer.write(payload)
        else:
            _write_report_atomic(args.output, payload)
        return 0 if report.execution_status == "passed" else 1
    except ArcanaValidationError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    except FileNotFoundError as exc:
        sys.stderr.write(f"benchmark report file not found: {exc.filename}\n")
        return 2
    except IsADirectoryError as exc:
        sys.stderr.write(f"benchmark report path is a directory: {exc.filename}\n")
        return 2
    except PermissionError as exc:
        sys.stderr.write(f"benchmark report permission denied: {exc.filename}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BENCHMARK_CLAIM_BOUNDARY",
    "BENCHMARK_EXECUTION_SUITE_FILENAME",
    "BENCHMARK_METRIC_DECIMAL_PLACES",
    "BENCHMARK_NUMERIC_REPORTING_POLICY",
    "BENCHMARK_RUNNER_VERSION",
    "BENCHMARK_RUN_REPORT_ID",
    "BENCHMARK_RUN_REPORT_SCHEMA_VERSION",
    "BenchmarkRunReport",
    "DecisionSnapshot",
    "InputManifestEntry",
    "MetricResult",
    "ScenarioRun",
    "build_input_manifest",
    "execute_benchmark_suite",
    "load_public_benchmark_execution_suite",
    "main",
    "report_json_bytes",
    "run_public_benchmark",
    "validate_execution_binding",
    "verify_benchmark_report",
    "verify_benchmark_report_against_source",
]
