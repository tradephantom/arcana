from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from arcana.bench import (
    BENCHMARK_EXECUTION_STATUS,
    PER_SCENARIO_REQUIRED_METRICS,
    REQUIRED_V01_METRICS,
    REQUIRED_V01_NEGATIVE_CONTROLS,
    REQUIRED_V01_THREAT_CLASSES,
    load_public_benchmark_scenarios,
    load_public_benchmark_suite,
    validate_benchmark_suite,
)
from arcana.errors import ArcanaValidationError, ReasonCode, SchemaVersion
from arcana.errors import Verdict
from arcana.model import BenchmarkScenario
from arcana.schemas import EXAMPLE_DIR, load_json, load_typed_fixture, validate_document


ROOT = Path(__file__).resolve().parents[1]


def _benchmark_documents() -> list[dict]:
    return [dict(load_json(path)) for path in sorted(EXAMPLE_DIR.glob("benchmark_*.synthetic.json"))]


def test_all_benchmark_fixtures_validate_schema_and_typed_contract() -> None:
    paths = sorted(EXAMPLE_DIR.glob("benchmark_*.synthetic.json"))
    assert paths

    for path in paths:
        document = load_json(path)
        validate_document(document, SchemaVersion.BENCHMARK_SCENARIO_V02)
        typed = load_typed_fixture(path)
        assert isinstance(typed, BenchmarkScenario)
        assert typed.synthetic is True


def test_public_benchmark_suite_covers_required_threat_classes_and_metrics() -> None:
    suite = load_public_benchmark_suite()

    assert suite.coverage.execution_status == BENCHMARK_EXECUTION_STATUS
    assert suite.coverage.scenario_count >= len(REQUIRED_V01_THREAT_CLASSES)
    assert suite.coverage.coverage_scenario_count >= len(REQUIRED_V01_THREAT_CLASSES)
    assert suite.coverage.negative_control_count >= len(REQUIRED_V01_NEGATIVE_CONTROLS)
    for threat_class in REQUIRED_V01_THREAT_CLASSES:
        assert threat_class in suite.coverage.threat_classes
    for metric in REQUIRED_V01_METRICS:
        assert metric in suite.coverage.reported_metrics
    for negative_control in REQUIRED_V01_NEGATIVE_CONTROLS:
        assert negative_control in suite.coverage.negative_controls


def test_every_scenario_separates_task_success_from_unsafe_actions_and_artifact_contract_validity() -> None:
    for scenario in load_public_benchmark_scenarios():
        for metric in PER_SCENARIO_REQUIRED_METRICS:
            assert metric in scenario.reported_metrics
        assert scenario.expected_response.reason_codes


def test_negative_controls_have_required_failure_modes_and_do_not_allow() -> None:
    scenarios = tuple(
        scenario for scenario in load_public_benchmark_scenarios() if scenario.scenario_type == "negative_control"
    )
    assert scenarios

    for scenario in scenarios:
        assert scenario.negative_control in REQUIRED_V01_NEGATIVE_CONTROLS
        for reason_code in REQUIRED_V01_NEGATIVE_CONTROLS[scenario.negative_control]:
            assert reason_code in scenario.expected_response.reason_codes
        assert scenario.expected_response.verdict not in {
            Verdict.ALLOW_BOUNDED_AUTONOMY,
            Verdict.ALLOW_WITH_CONTROLS,
        }


def test_suite_rejects_duplicate_scenario_ids() -> None:
    scenarios = load_public_benchmark_scenarios()
    duplicate = dataclasses.replace(scenarios[1], scenario_id=scenarios[0].scenario_id)

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_benchmark_suite((scenarios[0], duplicate, *scenarios[2:]))

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "benchmark_scenario_id_duplicate"


def test_suite_rejects_missing_per_scenario_unsafe_action_metric() -> None:
    scenarios = load_public_benchmark_scenarios()
    mutated = dataclasses.replace(
        scenarios[0],
        reported_metrics=tuple(metric for metric in scenarios[0].reported_metrics if metric != "unsafe_action_rate"),
    )

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_benchmark_suite((mutated, *scenarios[1:]))

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "benchmark_required_metric_missing"


def test_suite_rejects_incomplete_threat_coverage() -> None:
    scenarios = tuple(
        scenario
        for scenario in load_public_benchmark_scenarios()
        if scenario.threat_class != REQUIRED_V01_THREAT_CLASSES[0]
    )

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_benchmark_suite(scenarios)

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "benchmark_threat_coverage_incomplete"


def test_suite_rejects_incomplete_metric_coverage() -> None:
    scenarios = tuple(
        dataclasses.replace(
            scenario,
            reported_metrics=tuple(metric for metric in scenario.reported_metrics if metric != "human_intervention_efficiency"),
        )
        for scenario in load_public_benchmark_scenarios()
    )

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_benchmark_suite(scenarios)

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "benchmark_metric_coverage_incomplete"


def test_suite_rejects_missing_negative_control_coverage() -> None:
    missing = next(iter(REQUIRED_V01_NEGATIVE_CONTROLS))
    scenarios = tuple(
        scenario
        for scenario in load_public_benchmark_scenarios()
        if scenario.negative_control != missing
    )

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_benchmark_suite(scenarios)

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "benchmark_negative_control_coverage_incomplete"


def test_suite_rejects_negative_control_reason_code_mismatch() -> None:
    scenarios = load_public_benchmark_scenarios()
    target_index = next(
        index for index, scenario in enumerate(scenarios) if scenario.scenario_type == "negative_control"
    )
    target = scenarios[target_index]
    mutated = dataclasses.replace(
        target,
        expected_response=dataclasses.replace(
            target.expected_response,
            reason_codes=(ReasonCode.INFO_SYNTHETIC_FIXTURE,),
        ),
    )

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_benchmark_suite((*scenarios[:target_index], mutated, *scenarios[target_index + 1 :]))

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "benchmark_negative_control_reason_code_mismatch"


def test_suite_rejects_negative_control_allow_like_verdict() -> None:
    scenarios = load_public_benchmark_scenarios()
    target_index = next(
        index for index, scenario in enumerate(scenarios) if scenario.scenario_type == "negative_control"
    )
    target = scenarios[target_index]
    mutated = dataclasses.replace(
        target,
        expected_response=dataclasses.replace(
            target.expected_response,
            verdict=Verdict.ALLOW_WITH_CONTROLS,
        ),
    )

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_benchmark_suite((*scenarios[:target_index], mutated, *scenarios[target_index + 1 :]))

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "benchmark_negative_control_allows_admission"


def test_suite_rejects_coverage_scenario_with_negative_control_label() -> None:
    scenarios = load_public_benchmark_scenarios()
    target_index = next(
        index for index, scenario in enumerate(scenarios) if scenario.scenario_type == "coverage_scenario"
    )
    target = scenarios[target_index]
    mutated = dataclasses.replace(target, negative_control="stale_evidence")

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_benchmark_suite((*scenarios[:target_index], mutated, *scenarios[target_index + 1 :]))

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "benchmark_negative_control_unexpected"


def test_benchmark_documents_have_unique_graph_hashes() -> None:
    graph_hashes = [document["graph_fixture"]["graph_hash"] for document in _benchmark_documents()]

    assert len(graph_hashes) == len(set(graph_hashes))


def test_arcana_bench_document_tracks_negative_control_contract() -> None:
    text = (ROOT / "docs" / "ARCANA_BENCH_v0.1.md").read_text(encoding="utf-8")

    required_phrases = [
        "`coverage_scenario`",
        "`negative_control`",
        "`scenario_type: negative_control`",
        "suite validation rejects missing negative-control coverage",
        "allow-like negative-control verdicts",
        "synthetic_evaluator_execution_available",
        "invokes `arcana.decision.evaluate_decision`",
        "not_measured",
        "unavailable",
        "make bench",
    ]
    for negative_control in REQUIRED_V01_NEGATIVE_CONTROLS:
        required_phrases.append(f"`{negative_control}`")

    for phrase in required_phrases:
        assert phrase in text
