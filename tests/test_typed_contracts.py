from __future__ import annotations

import copy

import pytest

from arcana.calibration import CalibrationProfile
from arcana.certificate import BoundedAutonomyCertificate
from arcana.errors import ArcanaValidationError, ReasonCode
from arcana.model import BenchmarkScenario, FastGateContext, RiskContext
from arcana.schemas import EXAMPLE_DIR, load_json, load_typed_fixture, parse_typed_document


def _example(name: str) -> dict:
    return dict(load_json(EXAMPLE_DIR / name))


def test_public_examples_load_as_typed_documents() -> None:
    expected_types = {
        "benchmark_prompt_injection.synthetic.json": BenchmarkScenario,
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


def test_mutating_copy_does_not_modify_fixture() -> None:
    original = _example("risk_context_allow_with_controls.synthetic.json")
    mutated = copy.deepcopy(original)
    mutated["decision_horizon"]["duration_seconds"] = 1

    assert original["decision_horizon"]["duration_seconds"] == 300
    assert mutated["decision_horizon"]["duration_seconds"] == 1
