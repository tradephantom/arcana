"""Typed public inputs for deterministic ARCANA-Bench evaluator execution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from arcana._validation import (
    expect_bool,
    expect_datetime_string,
    expect_enum,
    expect_int_min,
    expect_mapping,
    expect_non_empty_string,
    expect_number_min,
    expect_number_range,
    expect_risk_model_version,
    expect_scenario_id,
    expect_sha256,
    expect_string_list,
    fail,
    require_value,
)
from arcana.calibration import CalibrationProfile
from arcana.decision import DecisionEvaluationRequest, DistillationAssessment
from arcana.errors import CalibrationLevel, CertificationStatus, ReasonCode
from arcana.matrices import MatrixBundle, TolerancePolicy, spectral_radius
from arcana.model import AutonomyBudget, DecisionHorizon, FastGateContext, LossBounds


BENCHMARK_EXECUTION_SCHEMA_VERSION = "arcana.benchmark_execution_suite.v0.1"
BENCHMARK_EVALUATOR_API = "arcana.decision.evaluate_decision.v0.1"
BENCHMARK_MATRIX_CONSTRUCTION = "normalized_sparse_pattern_v0.1"
MAX_BENCHMARK_MATRIX_DIMENSION = 256


def canonical_json_bytes(value: Any) -> bytes:
    """Return the canonical JSON representation used by benchmark hashes."""

    try:
        rendered = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        fail(
            "benchmark_canonical_json_invalid",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            f"value is not canonical JSON: {exc}",
            ("benchmark",),
        )
    return rendered.encode("ascii")


def sha256_json(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


@dataclass(frozen=True)
class BenchmarkMatrixInterval:
    construction: str
    dimension: int
    edge_count: int
    node_order: tuple[str, ...]
    matrix_graph_hash: str
    rho_lower_target: float
    rho_mean_target: float
    rho_upper_target: float

    @classmethod
    def from_mapping(
        cls,
        value: Any,
        path: tuple[str | int, ...] = ("matrix_interval",),
    ) -> "BenchmarkMatrixInterval":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        construction = expect_non_empty_string(
            require_value(data, "construction", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
            (*path, "construction"),
            ReasonCode.DENY_MODEL_INPUT_INVALID,
        )
        if construction != BENCHMARK_MATRIX_CONSTRUCTION:
            fail(
                "benchmark_matrix_construction_unsupported",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                f"matrix construction must be {BENCHMARK_MATRIX_CONSTRUCTION}",
                (*path, "construction"),
            )
        dimension = expect_int_min(
            require_value(data, "dimension", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
            1,
            (*path, "dimension"),
            ReasonCode.DENY_MODEL_INPUT_INVALID,
        )
        if dimension > MAX_BENCHMARK_MATRIX_DIMENSION:
            fail(
                "benchmark_matrix_dimension_too_large",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                f"matrix dimension must be <= {MAX_BENCHMARK_MATRIX_DIMENSION}",
                (*path, "dimension"),
            )
        edge_count = expect_int_min(
            require_value(data, "edge_count", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
            1,
            (*path, "edge_count"),
            ReasonCode.DENY_MODEL_INPUT_INVALID,
        )
        if edge_count > dimension * dimension:
            fail(
                "benchmark_matrix_edge_count_exceeds_capacity",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "edge_count cannot exceed dimension squared",
                (*path, "edge_count"),
            )
        node_order = expect_string_list(
            require_value(data, "node_order", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
            (*path, "node_order"),
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            min_items=1,
            unique=True,
        )
        if len(node_order) != dimension:
            fail(
                "benchmark_matrix_node_order_dimension_mismatch",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "node_order length must equal matrix dimension",
                (*path, "node_order"),
            )
        lower = expect_number_min(
            require_value(data, "rho_lower_target", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
            0,
            (*path, "rho_lower_target"),
            ReasonCode.DENY_MODEL_INPUT_INVALID,
        )
        mean = expect_number_min(
            require_value(data, "rho_mean_target", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
            0,
            (*path, "rho_mean_target"),
            ReasonCode.DENY_MODEL_INPUT_INVALID,
        )
        upper = expect_number_min(
            require_value(data, "rho_upper_target", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
            0,
            (*path, "rho_upper_target"),
            ReasonCode.DENY_MODEL_INPUT_INVALID,
        )
        if upper == 0:
            fail(
                "benchmark_matrix_rho_upper_target_nonpositive",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "rho_upper_target must be positive for a declared non-empty edge pattern",
                (*path, "rho_upper_target"),
            )
        if not lower <= mean <= upper:
            fail(
                "benchmark_matrix_rho_target_order_invalid",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "expected rho_lower_target <= rho_mean_target <= rho_upper_target",
                path,
            )
        return cls(
            construction=construction,
            dimension=dimension,
            edge_count=edge_count,
            node_order=node_order,
            matrix_graph_hash=expect_sha256(
                require_value(data, "matrix_graph_hash", path, ReasonCode.DENY_GRAPH_HASH_MISMATCH),
                (*path, "matrix_graph_hash"),
                ReasonCode.DENY_GRAPH_HASH_MISMATCH,
            ),
            rho_lower_target=lower,
            rho_mean_target=mean,
            rho_upper_target=upper,
        )

    def to_matrix_bundle(self) -> MatrixBundle:
        base = np.zeros((self.dimension, self.dimension), dtype=float)
        coordinates = [
            *((index, index) for index in range(self.dimension)),
            *(
                (row, column)
                for row in range(self.dimension)
                for column in range(self.dimension)
                if row != column
            ),
        ]
        for row, column in coordinates[: self.edge_count]:
            base[row, column] = 1.0
        base_radius = spectral_radius(base)
        if base_radius <= 0:
            fail(
                "benchmark_matrix_base_radius_nonpositive",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "normalized sparse pattern must have positive spectral radius",
                ("matrix_interval",),
            )

        def scaled(target: float) -> np.ndarray:
            return base * (target / base_radius)

        return MatrixBundle.from_values(
            scaled(self.rho_lower_target),
            scaled(self.rho_mean_target),
            scaled(self.rho_upper_target),
            node_order=self.node_order,
            graph_hash=self.matrix_graph_hash,
        )


@dataclass(frozen=True)
class BenchmarkEvaluatorInput:
    risk_model_version: str
    supported_risk_model_versions: tuple[str, ...]
    calibration_profile: CalibrationProfile
    decision_horizon: DecisionHorizon | None
    request_graph_hash: str
    matrix_interval: BenchmarkMatrixInterval
    rho_threshold: float
    autonomy_budget: AutonomyBudget
    decision_time: str
    required_calibration_level: CalibrationLevel
    loss_in_scope: bool
    loss_bounds: LossBounds | None
    fastgate: FastGateContext | None
    fastgate_required: bool
    required_controls: tuple[str, ...]
    available_controls: tuple[str, ...]
    human_gate_required: bool
    scope_reduction_required: bool
    scope_reduction_available: bool
    distillation: DistillationAssessment | None
    delta_rho_upper: float
    requested_external_requests: int
    requested_memory_writes: int
    requested_output_bytes: int
    tolerance_policy: TolerancePolicy
    input_hash: str

    @classmethod
    def from_mapping(
        cls,
        value: Any,
        path: tuple[str | int, ...] = ("evaluator_input",),
    ) -> "BenchmarkEvaluatorInput":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        risk_model_version = expect_risk_model_version(
            require_value(data, "risk_model_version", path, ReasonCode.DENY_RISK_MODEL_UNSUPPORTED),
            (*path, "risk_model_version"),
        )
        raw_supported = expect_string_list(
            require_value(data, "supported_risk_model_versions", path, ReasonCode.DENY_RISK_MODEL_UNSUPPORTED),
            (*path, "supported_risk_model_versions"),
            ReasonCode.DENY_RISK_MODEL_UNSUPPORTED,
            min_items=1,
            unique=True,
        )
        supported = tuple(
            expect_risk_model_version(item, (*path, "supported_risk_model_versions", index))
            for index, item in enumerate(raw_supported)
        )
        calibration_profile = CalibrationProfile.from_mapping(
            require_value(data, "calibration_profile", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
            (*path, "calibration_profile"),
        )
        if calibration_profile.level not in {CalibrationLevel.A0, CalibrationLevel.A1}:
            fail(
                "benchmark_synthetic_calibration_level_unsupported",
                ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
                "public synthetic execution suites are restricted to A0 or A1 calibration",
                (*path, "calibration_profile", "level"),
            )
        if calibration_profile.certification_status is not CertificationStatus.NON_CERTIFIABLE:
            fail(
                "benchmark_synthetic_profile_certifiable",
                ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
                "public synthetic execution profiles must be non_certifiable",
                (*path, "calibration_profile", "certification_status"),
            )
        raw_horizon = require_value(data, "decision_horizon", path, ReasonCode.DENY_DECISION_HORIZON_MISMATCH)
        decision_horizon = (
            None
            if raw_horizon is None
            else DecisionHorizon.from_mapping(raw_horizon, (*path, "decision_horizon"))
        )
        raw_loss_bounds = require_value(data, "loss_bounds", path, ReasonCode.DENY_LOSS_MODEL_INVALID)
        loss_bounds = (
            None
            if raw_loss_bounds is None
            else LossBounds.from_mapping(raw_loss_bounds, (*path, "loss_bounds"))
        )
        raw_fastgate = require_value(data, "fastgate", path, ReasonCode.DENY_FASTGATE_VECTOR_INVALID)
        fastgate = (
            None
            if raw_fastgate is None
            else FastGateContext.from_mapping(raw_fastgate, (*path, "fastgate"))
        )
        raw_distillation = require_value(data, "distillation", path, ReasonCode.DENY_DISTILLATION_RISK)
        distillation = _parse_distillation(raw_distillation, (*path, "distillation"))
        raw_tolerance = expect_mapping(
            require_value(data, "tolerance_policy", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
            (*path, "tolerance_policy"),
            ReasonCode.DENY_MODEL_INPUT_INVALID,
        )
        tolerance_policy = TolerancePolicy(
            abs_tolerance=expect_number_min(
                require_value(raw_tolerance, "abs_tolerance", (*path, "tolerance_policy"), ReasonCode.DENY_MODEL_INPUT_INVALID),
                0,
                (*path, "tolerance_policy", "abs_tolerance"),
                ReasonCode.DENY_MODEL_INPUT_INVALID,
            ),
            rel_tolerance=expect_number_min(
                require_value(raw_tolerance, "rel_tolerance", (*path, "tolerance_policy"), ReasonCode.DENY_MODEL_INPUT_INVALID),
                0,
                (*path, "tolerance_policy", "rel_tolerance"),
                ReasonCode.DENY_MODEL_INPUT_INVALID,
            ),
        )
        return cls(
            risk_model_version=risk_model_version,
            supported_risk_model_versions=supported,
            calibration_profile=calibration_profile,
            decision_horizon=decision_horizon,
            request_graph_hash=expect_sha256(
                require_value(data, "request_graph_hash", path, ReasonCode.DENY_GRAPH_HASH_MISMATCH),
                (*path, "request_graph_hash"),
                ReasonCode.DENY_GRAPH_HASH_MISMATCH,
            ),
            matrix_interval=BenchmarkMatrixInterval.from_mapping(
                require_value(data, "matrix_interval", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                (*path, "matrix_interval"),
            ),
            rho_threshold=expect_number_range(
                require_value(data, "rho_threshold", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                0,
                1,
                (*path, "rho_threshold"),
                ReasonCode.DENY_MODEL_INPUT_INVALID,
            ),
            autonomy_budget=AutonomyBudget.from_mapping(
                require_value(data, "autonomy_budget", path, ReasonCode.DENY_BUDGET_EXHAUSTED),
                (*path, "autonomy_budget"),
            ),
            decision_time=expect_datetime_string(
                require_value(data, "decision_time", path, ReasonCode.DENY_CONTEXT_STALE),
                (*path, "decision_time"),
                ReasonCode.DENY_CONTEXT_STALE,
            ),
            required_calibration_level=expect_enum(
                CalibrationLevel,
                require_value(data, "required_calibration_level", path, ReasonCode.DENY_CALIBRATION_INSUFFICIENT),
                (*path, "required_calibration_level"),
                ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
            ),
            loss_in_scope=expect_bool(
                require_value(data, "loss_in_scope", path, ReasonCode.DENY_LOSS_MODEL_INVALID),
                (*path, "loss_in_scope"),
                ReasonCode.DENY_LOSS_MODEL_INVALID,
            ),
            loss_bounds=loss_bounds,
            fastgate=fastgate,
            fastgate_required=expect_bool(
                require_value(data, "fastgate_required", path, ReasonCode.DENY_FASTGATE_UNCERTAIN),
                (*path, "fastgate_required"),
                ReasonCode.DENY_FASTGATE_UNCERTAIN,
            ),
            required_controls=expect_string_list(
                require_value(data, "required_controls", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                (*path, "required_controls"),
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                unique=True,
            ),
            available_controls=expect_string_list(
                require_value(data, "available_controls", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                (*path, "available_controls"),
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                unique=True,
            ),
            human_gate_required=expect_bool(
                require_value(data, "human_gate_required", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                (*path, "human_gate_required"),
                ReasonCode.DENY_MODEL_INPUT_INVALID,
            ),
            scope_reduction_required=expect_bool(
                require_value(data, "scope_reduction_required", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                (*path, "scope_reduction_required"),
                ReasonCode.DENY_MODEL_INPUT_INVALID,
            ),
            scope_reduction_available=expect_bool(
                require_value(data, "scope_reduction_available", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                (*path, "scope_reduction_available"),
                ReasonCode.DENY_MODEL_INPUT_INVALID,
            ),
            distillation=distillation,
            delta_rho_upper=expect_number_min(
                require_value(data, "delta_rho_upper", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                0,
                (*path, "delta_rho_upper"),
                ReasonCode.DENY_MODEL_INPUT_INVALID,
            ),
            requested_external_requests=expect_int_min(
                require_value(data, "requested_external_requests", path, ReasonCode.DENY_BUDGET_EXHAUSTED),
                0,
                (*path, "requested_external_requests"),
                ReasonCode.DENY_BUDGET_EXHAUSTED,
            ),
            requested_memory_writes=expect_int_min(
                require_value(data, "requested_memory_writes", path, ReasonCode.DENY_BUDGET_EXHAUSTED),
                0,
                (*path, "requested_memory_writes"),
                ReasonCode.DENY_BUDGET_EXHAUSTED,
            ),
            requested_output_bytes=expect_int_min(
                require_value(data, "requested_output_bytes", path, ReasonCode.DENY_BUDGET_EXHAUSTED),
                0,
                (*path, "requested_output_bytes"),
                ReasonCode.DENY_BUDGET_EXHAUSTED,
            ),
            tolerance_policy=tolerance_policy,
            input_hash=sha256_json(data),
        )

    def to_decision_request(self) -> DecisionEvaluationRequest:
        return DecisionEvaluationRequest(
            risk_model_version=self.risk_model_version,
            calibration_profile=self.calibration_profile,
            decision_horizon=self.decision_horizon,  # type: ignore[arg-type]
            graph_hash=self.request_graph_hash,
            matrix_bundle=self.matrix_interval.to_matrix_bundle(),
            rho_threshold=self.rho_threshold,
            autonomy_budget=self.autonomy_budget,
            decision_time=self.decision_time,
            required_calibration_level=self.required_calibration_level,
            loss_in_scope=self.loss_in_scope,
            loss_bounds=self.loss_bounds,
            fastgate=self.fastgate,
            fastgate_required=self.fastgate_required,
            required_controls=self.required_controls,
            available_controls=self.available_controls,
            human_gate_required=self.human_gate_required,
            scope_reduction_required=self.scope_reduction_required,
            scope_reduction_available=self.scope_reduction_available,
            distillation=self.distillation,
            delta_rho_upper=self.delta_rho_upper,
            requested_external_requests=self.requested_external_requests,
            requested_memory_writes=self.requested_memory_writes,
            requested_output_bytes=self.requested_output_bytes,
            tolerance_policy=self.tolerance_policy,
            supported_risk_model_versions=self.supported_risk_model_versions,
        )


@dataclass(frozen=True)
class BenchmarkExecutionCase:
    scenario_id: str
    evaluator_input: BenchmarkEvaluatorInput

    @classmethod
    def from_mapping(
        cls,
        value: Any,
        path: tuple[str | int, ...],
    ) -> "BenchmarkExecutionCase":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        return cls(
            scenario_id=expect_scenario_id(
                require_value(data, "scenario_id", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                (*path, "scenario_id"),
            ),
            evaluator_input=BenchmarkEvaluatorInput.from_mapping(
                require_value(data, "evaluator_input", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                (*path, "evaluator_input"),
            ),
        )


@dataclass(frozen=True)
class BenchmarkExecutionSuite:
    suite_id: str
    synthetic: bool
    evaluator_api: str
    cases: tuple[BenchmarkExecutionCase, ...]

    @classmethod
    def from_mapping(cls, value: Any, path: tuple[str | int, ...] = ()) -> "BenchmarkExecutionSuite":
        data = expect_mapping(value, path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        schema_version = expect_non_empty_string(
            require_value(data, "schema_version", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
            (*path, "schema_version"),
            ReasonCode.DENY_MODEL_INPUT_INVALID,
        )
        if schema_version != BENCHMARK_EXECUTION_SCHEMA_VERSION:
            fail(
                "benchmark_execution_schema_version_unsupported",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                f"schema_version must be {BENCHMARK_EXECUTION_SCHEMA_VERSION}",
                (*path, "schema_version"),
            )
        evaluator_api = expect_non_empty_string(
            require_value(data, "evaluator_api", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
            (*path, "evaluator_api"),
            ReasonCode.DENY_MODEL_INPUT_INVALID,
        )
        if evaluator_api != BENCHMARK_EVALUATOR_API:
            fail(
                "benchmark_evaluator_api_unsupported",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                f"evaluator_api must be {BENCHMARK_EVALUATOR_API}",
                (*path, "evaluator_api"),
            )
        raw_cases = require_value(data, "cases", path, ReasonCode.DENY_MODEL_INPUT_INVALID)
        if not isinstance(raw_cases, list) or not raw_cases:
            fail(
                "benchmark_execution_cases_invalid",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "cases must be a non-empty array",
                (*path, "cases"),
            )
        cases = tuple(
            BenchmarkExecutionCase.from_mapping(item, (*path, "cases", index))
            for index, item in enumerate(raw_cases)
        )
        scenario_ids = tuple(case.scenario_id for case in cases)
        if len(scenario_ids) != len(set(scenario_ids)):
            fail(
                "benchmark_execution_scenario_id_duplicate",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "execution case scenario_id values must be unique",
                (*path, "cases"),
            )
        if scenario_ids != tuple(sorted(scenario_ids)):
            fail(
                "benchmark_execution_case_order_invalid",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "execution cases must be sorted by scenario_id",
                (*path, "cases"),
            )
        profile_ids = tuple(case.evaluator_input.calibration_profile.profile_id for case in cases)
        if len(profile_ids) != len(set(profile_ids)):
            fail(
                "benchmark_execution_profile_id_duplicate",
                ReasonCode.DENY_CALIBRATION_INSUFFICIENT,
                "execution cases must use unique calibration profile ids",
                (*path, "cases"),
            )
        return cls(
            suite_id=expect_scenario_id(
                require_value(data, "suite_id", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                (*path, "suite_id"),
            ),
            synthetic=expect_bool(
                require_value(data, "synthetic", path, ReasonCode.DENY_MODEL_INPUT_INVALID),
                (*path, "synthetic"),
                ReasonCode.DENY_MODEL_INPUT_INVALID,
            ),
            evaluator_api=evaluator_api,
            cases=cases,
        )


def _parse_distillation(
    value: Any,
    path: tuple[str | int, ...],
) -> DistillationAssessment | None:
    if value is None:
        return None
    data = expect_mapping(value, path, ReasonCode.DENY_DISTILLATION_RISK)
    return DistillationAssessment(
        evidence_sufficient=expect_bool(
            require_value(data, "evidence_sufficient", path, ReasonCode.DENY_DISTILLATION_RISK),
            (*path, "evidence_sufficient"),
            ReasonCode.DENY_DISTILLATION_RISK,
        ),
        stable_operation=expect_bool(
            require_value(data, "stable_operation", path, ReasonCode.DENY_DISTILLATION_RISK),
            (*path, "stable_operation"),
            ReasonCode.DENY_DISTILLATION_RISK,
        ),
        scope_bounded=expect_bool(
            require_value(data, "scope_bounded", path, ReasonCode.DENY_DISTILLATION_RISK),
            (*path, "scope_bounded"),
            ReasonCode.DENY_DISTILLATION_RISK,
        ),
        invalidation_rules_declared=expect_bool(
            require_value(data, "invalidation_rules_declared", path, ReasonCode.DENY_DISTILLATION_RISK),
            (*path, "invalidation_rules_declared"),
            ReasonCode.DENY_DISTILLATION_RISK,
        ),
        required_calibration_level=expect_enum(
            CalibrationLevel,
            require_value(data, "required_calibration_level", path, ReasonCode.DENY_DISTILLATION_RISK),
            (*path, "required_calibration_level"),
            ReasonCode.DENY_DISTILLATION_RISK,
        ),
    )


__all__ = [
    "BENCHMARK_EVALUATOR_API",
    "BENCHMARK_EXECUTION_SCHEMA_VERSION",
    "BENCHMARK_MATRIX_CONSTRUCTION",
    "MAX_BENCHMARK_MATRIX_DIMENSION",
    "BenchmarkEvaluatorInput",
    "BenchmarkExecutionCase",
    "BenchmarkExecutionSuite",
    "BenchmarkMatrixInterval",
    "canonical_json_bytes",
    "sha256_json",
]
