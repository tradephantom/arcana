from __future__ import annotations

import dataclasses

import pytest

from arcana.bench import (
    PER_SCENARIO_REQUIRED_METRICS,
    REQUIRED_V01_METRICS,
    REQUIRED_V01_THREAT_CLASSES,
    load_public_benchmark_scenarios,
    load_public_benchmark_suite,
    validate_benchmark_suite,
)
from arcana.errors import ArcanaValidationError, ReasonCode, SchemaVersion
from arcana.model import BenchmarkScenario
from arcana.schemas import EXAMPLE_DIR, load_json, load_typed_fixture, validate_document


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

    assert suite.coverage.scenario_count >= len(REQUIRED_V01_THREAT_CLASSES)
    for threat_class in REQUIRED_V01_THREAT_CLASSES:
        assert threat_class in suite.coverage.threat_classes
    for metric in REQUIRED_V01_METRICS:
        assert metric in suite.coverage.reported_metrics


def test_every_scenario_separates_task_success_from_unsafe_actions_and_artifact_contract_validity() -> None:
    for scenario in load_public_benchmark_scenarios():
        for metric in PER_SCENARIO_REQUIRED_METRICS:
            assert metric in scenario.reported_metrics
        assert scenario.expected_response.reason_codes


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


def test_benchmark_documents_have_unique_graph_hashes() -> None:
    graph_hashes = [document["graph_fixture"]["graph_hash"] for document in _benchmark_documents()]

    assert len(graph_hashes) == len(set(graph_hashes))
