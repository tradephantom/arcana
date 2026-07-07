from __future__ import annotations

import copy

import pytest

from arcana.errors import ArcanaValidationError, ReasonCode
from arcana.schemas import EXAMPLE_DIR, load_json, parse_typed_document, validate_document


def _example(name: str) -> dict:
    return dict(load_json(EXAMPLE_DIR / name))


def test_missing_risk_model_version_maps_to_specific_reason() -> None:
    document = _example("calibration_profile_a0.synthetic.json")
    del document["risk_model_version"]

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_RISK_MODEL_UNSUPPORTED
    assert exc_info.value.code == "schema_required_risk_model_version"


def test_missing_decision_horizon_maps_to_specific_reason() -> None:
    document = _example("risk_context_allow_with_controls.synthetic.json")
    del document["decision_horizon"]

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_DECISION_HORIZON_MISMATCH
    assert exc_info.value.code == "schema_required_decision_horizon"


def test_missing_graph_hash_maps_to_specific_reason() -> None:
    document = _example("risk_context_allow_with_controls.synthetic.json")
    del document["graph_hash"]

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_GRAPH_HASH_MISMATCH
    assert exc_info.value.code == "schema_required_graph_hash"


def test_fastgate_missing_method_maps_to_vector_invalid() -> None:
    document = _example("risk_context_allow_with_controls.synthetic.json")
    del document["fastgate"]["positive_vector_method"]

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_FASTGATE_VECTOR_INVALID
    assert exc_info.value.code == "schema_required_positive_vector_method"


def test_missing_certificate_loss_bounds_maps_to_loss_model_invalid() -> None:
    document = _example("certificate_a0_non_certifiable.synthetic.json")
    del document["loss_bounds"]

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_LOSS_MODEL_INVALID
    assert exc_info.value.code == "schema_required_loss_bounds"


def test_context_schema_rejects_rho_threshold_above_subcritical_limit() -> None:
    document = copy.deepcopy(_example("risk_context_allow_with_controls.synthetic.json"))
    document["rho_interval"]["threshold"] = 1.01

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "schema_maximum_threshold"


def test_certificate_schema_rejects_rho_threshold_above_subcritical_limit() -> None:
    document = copy.deepcopy(_example("certificate_a0_non_certifiable.synthetic.json"))
    document["rho_interval"]["threshold"] = 1.01

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "schema_maximum_threshold"


def test_unsupported_schema_version_maps_to_model_input_invalid() -> None:
    document = _example("risk_context_allow_with_controls.synthetic.json")
    document["schema_version"] = "arcana.context.v9.9"

    with pytest.raises(ArcanaValidationError) as exc_info:
        validate_document(document)

    assert exc_info.value.reason_code is ReasonCode.DENY_MODEL_INPUT_INVALID
    assert exc_info.value.code == "schema_version_unsupported"


def test_schema_valid_then_typed_contract_validates_public_context() -> None:
    document = copy.deepcopy(_example("risk_context_allow_with_controls.synthetic.json"))
    typed = parse_typed_document(document)

    assert typed.risk_model_version == "arcana.risk.v0.2"
    assert typed.fastgate is not None
    assert typed.fastgate.upper_bound == 0.72
