from __future__ import annotations

import json
import re
from pathlib import Path

from arcana.errors import SchemaVersion
from arcana.schemas import validate_document


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "PUBLIC_INTEGRATION_CONTRACT_v0.1.md"


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def _json_blocks(text: str) -> list[dict[str, object]]:
    blocks = re.findall(r"```json\n(.*?)\n```", text, flags=re.DOTALL)
    assert blocks, "integration contract must include public JSON examples"
    return [json.loads(block) for block in blocks]


def test_public_integration_contract_sections_are_present() -> None:
    text = _doc_text()

    required_headings = [
        "# ARCANA Public Integration Contract v0.1",
        "## 1. Contract Rule",
        "## 3. Public Artifact Import",
        "## 4. Risk Context Export Shape",
        "## 5. Certificate Import and Export Shape",
        "## 6. Evidence Hash Requirements",
        "## 7. Reason-Code Bridge",
        "## 8. Public vs Integration-Private Field Boundary",
        "## 9. Freshness and Recompute Rules",
        "## 10. Integration Non-Goals",
        "## 11. Conformance Checklist",
    ]

    for heading in required_headings:
        assert heading in text


def test_public_integration_contract_examples_are_schema_shaped() -> None:
    import_request, risk_context = _json_blocks(_doc_text())

    assert import_request["risk_model_version"] == "arcana.risk.v0.2"
    assert import_request["calibration_profile_id"] == "arcana.cal.example_profile"
    assert isinstance(import_request["decision_horizon"], dict)
    assert import_request["evidence"]["synthetic"] is True

    assert risk_context["schema_version"] == "arcana.context.v0.2"
    assert risk_context["calibration_level"] == "A0"
    assert risk_context["decision"] == "observe_only"
    assert "ARCANA_REQUIRE_OBSERVE_ONLY" in risk_context["reason_codes"]
    assert "ARCANA_INFO_A0_NON_CERTIFIABLE" in risk_context["reason_codes"]
    assert risk_context["evidence"]["synthetic"] is True
    assert risk_context["fastgate"]["mode"] == "observe_only"

    validate_document(risk_context, SchemaVersion.CONTEXT_V02)


def test_public_integration_contract_preserves_reason_code_bridge() -> None:
    text = _doc_text()

    required_bridge_entries = [
        "ARCANA_ALLOW_BOUNDED_AUTONOMY",
        "ARCANA_ALLOW_WITH_CONTROLS",
        "ARCANA_REQUIRE_SCOPE_REDUCTION",
        "ARCANA_REQUIRE_HUMAN_GATE",
        "ARCANA_REQUIRE_OBSERVE_ONLY",
        "ARCANA_DENY_*",
        "ARCANA_INFO_*",
    ]

    for entry in required_bridge_entries:
        assert entry in text

    assert "must not collapse distinct ARCANA denial codes" in text


def test_public_integration_contract_keeps_certificate_boundary_explicit() -> None:
    text = _doc_text()

    assert "A0 output is non-certifiable" in text
    assert "must not emit a certifiable production artifact from A0 calibration" in text
    assert "proof of absolute safety" in text
    assert "risk-elimination guarantees" in text


def test_public_integration_contract_has_hash_and_recompute_requirements() -> None:
    text = _doc_text()

    assert "sha256:<64 hex chars>" in text
    assert "canonicalization method" in text
    assert "Unknown compatibility state means risky" in text
    assert "FastGate returns uncertain or vector-invalid status" in text

    hash_values = re.findall(r"sha256:[a-f0-9]{64}", text)
    assert len(hash_values) >= 2


def test_public_integration_contract_has_no_private_boundary_tokens() -> None:
    text = _doc_text()
    forbidden_tokens = [
        "/".join(("", "Users", "")),
        "file" + "://",
        "/".join(("docs", "canonical")),
        "provenance" + "/",
        "internal" + "/",
        "_".join(("CBE", "DENY", "")),
        "_".join(("CBE", "REQUIRE", "")),
        "AX" + "CP Enterprise",
        "NEM" + "ORG",
    ]

    for token in forbidden_tokens:
        assert token not in text
