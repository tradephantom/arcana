from __future__ import annotations

import copy

import pytest

from arcana.calibration import CalibrationProfile
from arcana.benchmark_input import BenchmarkExecutionSuite
from arcana.certificate import BoundedAutonomyCertificate
from arcana.errors import ArcanaValidationError, ReasonCode
from arcana.model import BenchmarkScenario, DecisionResult, FastGateContext, GraphDelta, GraphState, RiskContext
from arcana.schemas import EXAMPLE_DIR, load_json, load_typed_fixture, parse_typed_document


def _example(name: str) -> dict:
    return dict(load_json(EXAMPLE_DIR / name))


def test_public_examples_load_as_typed_documents() -> None:
    expected_types = {
        "benchmark_prompt_injection.synthetic.json": BenchmarkScenario,
        "arcana_bench_execution_suite.synthetic.json": BenchmarkExecutionSuite,
        "calibration_profile_a0.synthetic.json": CalibrationProfile,
        "risk_context_allow_with_controls.synthetic.json": RiskContext,
        "certificate_a0_non_certifiable.synthetic.json": BoundedAutonomyCertificate,
    }

    for filename, expected_type in expected_types.items():
        loaded = load_typed_fixture(EXAMPLE_DIR / filename)
        assert isinstance(loaded, expected_type)


def test_context_typed_contract_rejects_rho_interval_order() -> None:
    document = _example("risk_context_allow_with_controls.synthetic.json")
    document["rho_interval"] = {
        "lower": 0.7,
        "mean": 0.6,
        "upper": 0.8,
        "threshold": 0.9,
    }

    with pytest.raises(ArcanaValidationError) as exc_info:
        parse_typed_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "rho_interval_order_invalid"


def test_fastgate_contract_requires_positive_vector_method() -> None:
    with pytest.raises(ArcanaValidationError) as exc_info:
        FastGateContext.from_mapping({"mode": "perron_collatz_bound", "upper_bound": 0.7})

    assert exc_info.value.reason_code is ReasonCode.DENY_FASTGATE_VECTOR_INVALID
    assert exc_info.value.code == "fastgate_positive_vector_method_missing"


def test_a0_calibration_must_be_non_certifiable() -> None:
    document = _example("calibration_profile_a0.synthetic.json")
    document["certification_status"] = "certifiable_under_profile"

    with pytest.raises(ArcanaValidationError) as exc_info:
        parse_typed_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_CALIBRATION_INSUFFICIENT


def test_a1_calibration_must_be_non_certifiable() -> None:
    document = _example("calibration_profile_a0.synthetic.json")
    document["level"] = "A1"
    document["source"] = ["static_conservative_prior"]
    document["certification_status"] = "certifiable_under_profile"

    with pytest.raises(ArcanaValidationError) as exc_info:
        parse_typed_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_CALIBRATION_INSUFFICIENT


def test_runtime_observation_requires_a3_calibration() -> None:
    document = _example("calibration_profile_a0.synthetic.json")
    document["level"] = "A2"
    document["source"] = ["runtime_observation"]
    document["certification_status"] = "certifiable_under_profile"

    with pytest.raises(ArcanaValidationError) as exc_info:
        parse_typed_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_CALIBRATION_INSUFFICIENT


def test_a2_requires_empirical_or_redteam_evidence() -> None:
    document = _example("calibration_profile_a0.synthetic.json")
    document["level"] = "A2"
    document["source"] = ["static_conservative_prior"]
    document["certification_status"] = "certifiable_under_profile"

    with pytest.raises(ArcanaValidationError) as exc_info:
        CalibrationProfile.from_mapping(document)

    assert exc_info.value.code == "calibration_level_evidence_missing"


def test_a3_requires_runtime_observation() -> None:
    document = _example("calibration_profile_a0.synthetic.json")
    document["level"] = "A3"
    document["source"] = ["controlled_redteam"]
    document["certification_status"] = "certifiable_under_profile"

    with pytest.raises(ArcanaValidationError) as exc_info:
        CalibrationProfile.from_mapping(document)

    assert exc_info.value.code == "calibration_level_evidence_missing"


def test_a2_accepts_qualifying_non_synthetic_source_class() -> None:
    document = _example("calibration_profile_a0.synthetic.json")
    document["level"] = "A2"
    document["source"] = ["static_conservative_prior", "controlled_redteam"]
    document["certification_status"] = "certifiable_under_profile"

    parsed = parse_typed_document(document)

    assert isinstance(parsed, CalibrationProfile)


def test_synthetic_public_benchmark_does_not_qualify_a2_profile() -> None:
    document = _example("calibration_profile_a0.synthetic.json")
    document["level"] = "A2"
    document["source"] = ["public_benchmark"]
    document["certification_status"] = "non_certifiable"

    with pytest.raises(ArcanaValidationError) as exc_info:
        CalibrationProfile.from_mapping(document)

    assert exc_info.value.code == "calibration_level_evidence_missing"


def test_empirical_public_benchmark_qualifies_a2_profile() -> None:
    document = _example("calibration_profile_a0.synthetic.json")
    document["level"] = "A2"
    document["source"] = ["empirical_public_benchmark"]
    document["certification_status"] = "certifiable_under_profile"

    parsed = parse_typed_document(document)

    assert isinstance(parsed, CalibrationProfile)


def test_certifiable_profile_rejects_synthetic_public_benchmark_source() -> None:
    document = _example("calibration_profile_a0.synthetic.json")
    document["level"] = "A2"
    document["source"] = ["controlled_redteam", "public_benchmark"]
    document["certification_status"] = "certifiable_under_profile"

    with pytest.raises(ArcanaValidationError) as exc_info:
        CalibrationProfile.from_mapping(document)

    assert exc_info.value.code == "certifiable_profile_synthetic_source_invalid"


def test_mutating_copy_does_not_modify_fixture() -> None:
    original = _example("risk_context_allow_with_controls.synthetic.json")
    mutated = copy.deepcopy(original)
    mutated["decision_horizon"]["duration_seconds"] = 1

    assert original["decision_horizon"]["duration_seconds"] == 300
    assert mutated["decision_horizon"]["duration_seconds"] == 1


def test_graph_state_rejects_empty_and_duplicate_nodes() -> None:
    graph_hash = "sha256:" + "1" * 64
    with pytest.raises(ArcanaValidationError) as empty_exc:
        GraphState.from_mapping({"graph_hash": graph_hash, "nodes": [], "edges": []})
    assert empty_exc.value.code == "graph_nodes_empty"

    duplicate_nodes = [
        {"node_id": "agent", "node_class": "A"},
        {"node_id": "agent", "node_class": "T"},
    ]
    with pytest.raises(ArcanaValidationError) as duplicate_exc:
        GraphState.from_mapping({"graph_hash": graph_hash, "nodes": duplicate_nodes, "edges": []})
    assert duplicate_exc.value.code == "graph_node_id_duplicate"


def test_graph_state_and_delta_reject_duplicate_edges() -> None:
    graph_hash = "sha256:" + "2" * 64
    nodes = [
        {"node_id": "agent", "node_class": "A"},
        {"node_id": "tool", "node_class": "T"},
    ]
    edge = {"source": "agent", "target": "tool", "edge_type": "invoke"}
    with pytest.raises(ArcanaValidationError) as graph_exc:
        GraphState.from_mapping({"graph_hash": graph_hash, "nodes": nodes, "edges": [edge, edge]})
    assert graph_exc.value.code == "graph_edge_duplicate"

    with pytest.raises(ArcanaValidationError) as delta_exc:
        GraphDelta.from_mapping({"delta_hash": graph_hash, "added_edges": [edge, edge]})
    assert delta_exc.value.code == "graph_delta_edge_duplicate"


def test_typed_results_reject_duplicate_reason_codes_and_non_mapping_metrics() -> None:
    with pytest.raises(ArcanaValidationError) as duplicate_exc:
        DecisionResult.from_mapping(
            {
                "verdict": "deny",
                "reason_codes": ["ARCANA_DENY_MODEL_INPUT_INVALID", "ARCANA_DENY_MODEL_INPUT_INVALID"],
            }
        )
    assert duplicate_exc.value.code == "reason_codes_not_unique"

    with pytest.raises(ArcanaValidationError) as metrics_exc:
        DecisionResult.from_mapping(
            {
                "verdict": "deny",
                "reason_codes": ["ARCANA_DENY_MODEL_INPUT_INVALID"],
                "metrics": "not-an-object",
            }
        )
    assert metrics_exc.value.code == "object_expected"


def test_artifact_typed_contracts_reject_duplicate_reason_codes_without_schema_gate() -> None:
    context = _example("risk_context_allow_with_controls.synthetic.json")
    context["reason_codes"] = ["ARCANA_ALLOW_WITH_CONTROLS", "ARCANA_ALLOW_WITH_CONTROLS"]
    with pytest.raises(ArcanaValidationError) as context_exc:
        RiskContext.from_mapping(context)
    assert context_exc.value.code == "reason_codes_not_unique"

    certificate = _example("certificate_a0_non_certifiable.synthetic.json")
    certificate["reason_codes"] = ["ARCANA_REQUIRE_OBSERVE_ONLY", "ARCANA_REQUIRE_OBSERVE_ONLY"]
    with pytest.raises(ArcanaValidationError) as certificate_exc:
        BoundedAutonomyCertificate.from_mapping(certificate)
    assert certificate_exc.value.code == "reason_codes_not_unique"
