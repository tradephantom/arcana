"""ARCANA-Bench public synthetic scenario suite validation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from arcana._validation import fail
from arcana.errors import ReasonCode, Verdict
from arcana.model import BenchmarkScenario
from arcana.schemas import EXAMPLE_DIR, load_typed_fixture


BENCHMARK_SCENARIO_GLOB = "benchmark_*.synthetic.json"
REQUIRED_V01_THREAT_CLASSES = (
    "indirect_prompt_injection",
    "persistent_memory_poisoning",
    "tool_misuse",
    "unsafe_delegation_loop",
    "benchmark_gaming",
    "dynamic_execution_abuse",
)
REQUIRED_V01_METRICS = (
    "task_success_rate",
    "unsafe_action_rate",
    "policy_violation_rate",
    "delta_rho_upper",
    "rho_peak",
    "AaR_99_upper",
    "AES_99_upper",
    "containment_time_steps",
    "autonomy_budget_consumed",
    "human_intervention_efficiency",
    "artifact_contract_validity_rate",
)
REQUIRED_V01_NEGATIVE_CONTROLS: dict[str, tuple[ReasonCode, ...]] = {
    "missing_decision_horizon": (ReasonCode.DENY_DECISION_HORIZON_MISMATCH,),
    "graph_hash_mismatch": (ReasonCode.DENY_GRAPH_HASH_MISMATCH,),
    "a0_artifact_used_for_admission": (
        ReasonCode.REQUIRE_OBSERVE_ONLY,
        ReasonCode.INFO_A0_NON_CERTIFIABLE,
    ),
    "rho_mean_below_threshold_rho_upper_above_threshold": (ReasonCode.DENY_RHO_UPPER_BOUND,),
    "fastgate_inconclusive": (ReasonCode.DENY_FASTGATE_UNCERTAIN,),
    "loss_model_missing_required": (ReasonCode.DENY_LOSS_MODEL_INVALID,),
    "stale_evidence": (ReasonCode.DENY_CONTEXT_STALE,),
}
PER_SCENARIO_REQUIRED_METRICS = (
    "task_success_rate",
    "unsafe_action_rate",
    "artifact_contract_validity_rate",
)
PER_SCENARIO_RISK_METRICS = (
    "policy_violation_rate",
    "delta_rho_upper",
    "rho_peak",
    "AaR_99_upper",
    "AES_99_upper",
    "autonomy_budget_consumed",
)


@dataclass(frozen=True)
class BenchmarkSuiteCoverage:
    scenario_count: int
    coverage_scenario_count: int
    negative_control_count: int
    threat_classes: tuple[str, ...]
    reported_metrics: tuple[str, ...]
    negative_controls: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkSuite:
    scenarios: tuple[BenchmarkScenario, ...]
    coverage: BenchmarkSuiteCoverage


def load_public_benchmark_scenarios(example_dir: Path = EXAMPLE_DIR) -> tuple[BenchmarkScenario, ...]:
    paths = sorted(example_dir.glob(BENCHMARK_SCENARIO_GLOB))
    if not paths:
        fail(
            "benchmark_scenarios_missing",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "no benchmark scenario fixtures found",
            ("examples",),
        )
    scenarios: list[BenchmarkScenario] = []
    for path in paths:
        loaded = load_typed_fixture(path)
        if not isinstance(loaded, BenchmarkScenario):
            fail(
                "benchmark_fixture_type_invalid",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "benchmark fixture did not parse as BenchmarkScenario",
                (str(path),),
            )
        scenarios.append(loaded)
    return tuple(scenarios)


def load_public_benchmark_suite(example_dir: Path = EXAMPLE_DIR) -> BenchmarkSuite:
    return validate_benchmark_suite(load_public_benchmark_scenarios(example_dir))


def validate_benchmark_suite(scenarios: Iterable[BenchmarkScenario]) -> BenchmarkSuite:
    normalized = tuple(scenarios)
    if not normalized:
        fail(
            "benchmark_scenarios_missing",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "benchmark suite requires at least one scenario",
            ("benchmark_suite",),
        )
    _validate_unique_scenario_ids(normalized)
    for index, scenario in enumerate(normalized):
        _validate_scenario_contract(scenario, index)
    coverage_scenarios = tuple(scenario for scenario in normalized if scenario.scenario_type == "coverage_scenario")
    negative_control_scenarios = tuple(scenario for scenario in normalized if scenario.scenario_type == "negative_control")
    threat_classes = tuple(sorted({scenario.threat_class for scenario in coverage_scenarios}))
    reported_metrics = tuple(sorted({metric for scenario in normalized for metric in scenario.reported_metrics}))
    negative_controls = tuple(sorted({str(scenario.negative_control) for scenario in negative_control_scenarios}))
    _validate_required_threat_coverage(threat_classes)
    _validate_required_metric_coverage(reported_metrics)
    _validate_required_negative_controls(negative_control_scenarios, negative_controls)
    return BenchmarkSuite(
        scenarios=normalized,
        coverage=BenchmarkSuiteCoverage(
            scenario_count=len(normalized),
            coverage_scenario_count=len(coverage_scenarios),
            negative_control_count=len(negative_control_scenarios),
            threat_classes=threat_classes,
            reported_metrics=reported_metrics,
            negative_controls=negative_controls,
        ),
    )


def _validate_unique_scenario_ids(scenarios: tuple[BenchmarkScenario, ...]) -> None:
    seen: set[str] = set()
    for index, scenario in enumerate(scenarios):
        if scenario.scenario_id in seen:
            fail(
                "benchmark_scenario_id_duplicate",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                "benchmark scenario_id values must be unique",
                ("benchmark_suite", index, "scenario_id"),
            )
        seen.add(scenario.scenario_id)


def _validate_scenario_contract(scenario: BenchmarkScenario, index: int) -> None:
    if not isinstance(scenario, BenchmarkScenario):
        fail(
            "benchmark_scenario_invalid",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "benchmark suite entries must be BenchmarkScenario",
            ("benchmark_suite", index),
        )
    if scenario.scenario_type not in {"coverage_scenario", "negative_control"}:
        fail(
            "benchmark_scenario_type_invalid",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "benchmark scenario_type must be coverage_scenario or negative_control",
            ("benchmark_suite", index, "scenario_type"),
        )
    if scenario.scenario_type == "coverage_scenario" and scenario.negative_control is not None:
        fail(
            "benchmark_negative_control_unexpected",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "coverage scenarios must not declare negative_control",
            ("benchmark_suite", index, "negative_control"),
        )
    if scenario.scenario_type == "negative_control" and scenario.negative_control is None:
        fail(
            "benchmark_negative_control_missing",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "negative_control scenarios must declare negative_control",
            ("benchmark_suite", index, "negative_control"),
        )
    if not scenario.synthetic:
        fail(
            "benchmark_scenario_not_synthetic",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "public ARCANA-Bench scenarios must be synthetic",
            ("benchmark_suite", index, "synthetic"),
        )
    for metric in PER_SCENARIO_REQUIRED_METRICS:
        if metric not in scenario.reported_metrics:
            fail(
                "benchmark_required_metric_missing",
                ReasonCode.DENY_MODEL_INPUT_INVALID,
                f"{metric} is required for each benchmark scenario",
                ("benchmark_suite", index, "reported_metrics"),
            )
    if not any(metric in scenario.reported_metrics for metric in PER_SCENARIO_RISK_METRICS):
        fail(
            "benchmark_risk_metric_missing",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "each scenario must report at least one risk metric",
            ("benchmark_suite", index, "reported_metrics"),
        )
    if not scenario.expected_response.reason_codes:
        fail(
            "benchmark_risk_bound_status_missing",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "expected response must expose risk-bound status with reason codes",
            ("benchmark_suite", index, "expected_arcana_response"),
        )
    if scenario.scenario_type == "negative_control":
        _validate_negative_control_contract(scenario, index)


def _validate_required_threat_coverage(threat_classes: tuple[str, ...]) -> None:
    missing = tuple(threat_class for threat_class in REQUIRED_V01_THREAT_CLASSES if threat_class not in threat_classes)
    if missing:
        fail(
            "benchmark_threat_coverage_incomplete",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "ARCANA-Bench v0.1 threat-class coverage is incomplete",
            ("benchmark_suite", "threat_classes"),
        )


def _validate_required_metric_coverage(reported_metrics: tuple[str, ...]) -> None:
    missing = tuple(metric for metric in REQUIRED_V01_METRICS if metric not in reported_metrics)
    if missing:
        fail(
            "benchmark_metric_coverage_incomplete",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "ARCANA-Bench v0.1 metric coverage is incomplete",
            ("benchmark_suite", "reported_metrics"),
        )


def _validate_required_negative_controls(
    scenarios: tuple[BenchmarkScenario, ...],
    negative_controls: tuple[str, ...],
) -> None:
    if not scenarios:
        fail(
            "benchmark_negative_controls_missing",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "ARCANA-Bench v0.1 requires public negative-control fixtures",
            ("benchmark_suite", "negative_controls"),
        )
    missing = tuple(control for control in REQUIRED_V01_NEGATIVE_CONTROLS if control not in negative_controls)
    if missing:
        fail(
            "benchmark_negative_control_coverage_incomplete",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "ARCANA-Bench v0.1 negative-control coverage is incomplete",
            ("benchmark_suite", "negative_controls"),
        )


def _validate_negative_control_contract(scenario: BenchmarkScenario, index: int) -> None:
    negative_control = scenario.negative_control
    if negative_control not in REQUIRED_V01_NEGATIVE_CONTROLS:
        fail(
            "benchmark_negative_control_unknown",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "benchmark negative_control is not required by ARCANA-Bench v0.1",
            ("benchmark_suite", index, "negative_control"),
        )
    required_codes = REQUIRED_V01_NEGATIVE_CONTROLS[negative_control]
    missing_codes = tuple(code for code in required_codes if code not in scenario.expected_response.reason_codes)
    if missing_codes:
        fail(
            "benchmark_negative_control_reason_code_mismatch",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "benchmark negative_control does not expose the required ARCANA reason code",
            ("benchmark_suite", index, "expected_arcana_response", "reason_codes"),
        )
    if scenario.expected_response.verdict in {Verdict.ALLOW_BOUNDED_AUTONOMY, Verdict.ALLOW_WITH_CONTROLS}:
        fail(
            "benchmark_negative_control_allows_admission",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "benchmark negative_control must not use an allow-like verdict",
            ("benchmark_suite", index, "expected_arcana_response", "verdict"),
        )


__all__ = [
    "BENCHMARK_SCENARIO_GLOB",
    "PER_SCENARIO_REQUIRED_METRICS",
    "PER_SCENARIO_RISK_METRICS",
    "REQUIRED_V01_METRICS",
    "REQUIRED_V01_NEGATIVE_CONTROLS",
    "REQUIRED_V01_THREAT_CLASSES",
    "BenchmarkSuite",
    "BenchmarkSuiteCoverage",
    "load_public_benchmark_scenarios",
    "load_public_benchmark_suite",
    "validate_benchmark_suite",
]
