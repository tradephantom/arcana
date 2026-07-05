from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "ARCANA_Whitepaper_v0.2_Draft.md"


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_whitepaper_draft_sections_are_present() -> None:
    text = _doc_text()

    required_headings = [
        "# ARCANA: Model-Bounded Autonomy Accounting for Agentic Systems",
        "## Abstract",
        "## 1. Paper Rule",
        "## 2. Problem",
        "## 4. Model Overview",
        "## 7. Uncertainty and Spectral Risk",
        "## 8. Loss Is Separate From Propagation",
        "## 9. Calibration",
        "## 11. Decision Semantics",
        "## 12. Certificate-Like Artifacts",
        "## 13. FastGate",
        "## 15. ARCANA-Bench",
        "## 16. Reference Implementation",
        "## 17. Public Integration Contract",
        "## 18. Limitations",
        "## 21. Draft Status",
    ]

    for heading in required_headings:
        assert heading in text


def test_whitepaper_draft_preserves_model_claim_boundaries() -> None:
    text = _doc_text()

    required_boundaries = [
        "model-bounded autonomy accounting",
        "not a production control plane",
        "Admission-like decisions use `rho_upper`, not `rho_mean`",
        "K = unsafe propagation pressure",
        "L = impact or loss",
        "A0 is demo-only",
        "A0 artifacts are non-certifiable",
        "Task success is not an ARCANA safety score",
        "FastGate is not a weaker model",
        "ARCANA remains enforcement-neutral",
    ]

    for boundary in required_boundaries:
        assert boundary in text


def test_whitepaper_draft_covers_registered_reason_code_paths() -> None:
    text = _doc_text()

    required_codes = [
        "ARCANA_DENY_DECISION_HORIZON_MISMATCH",
        "ARCANA_DENY_MODEL_INPUT_INVALID",
        "ARCANA_DENY_RHO_UPPER_BOUND",
        "ARCANA_DENY_LOSS_MODEL_INVALID",
        "ARCANA_DENY_AAR_UPPER_BOUND",
        "ARCANA_DENY_AES_UPPER_BOUND",
        "ARCANA_INFO_A0_NON_CERTIFIABLE",
        "ARCANA_DENY_CALIBRATION_INSUFFICIENT",
        "ARCANA_REQUIRE_OBSERVE_ONLY",
        "ARCANA_DENY_RISK_MODEL_UNSUPPORTED",
        "ARCANA_DENY_CONTEXT_STALE",
        "ARCANA_DENY_GRAPH_HASH_MISMATCH",
        "ARCANA_DENY_BUDGET_EXHAUSTED",
        "ARCANA_REQUIRE_SCOPE_REDUCTION",
        "ARCANA_REQUIRE_HUMAN_GATE",
        "ARCANA_DENY_FASTGATE_UNCERTAIN",
        "ARCANA_DENY_FASTGATE_VECTOR_INVALID",
        "ARCANA_DENY_DISTILLATION_RISK",
    ]

    for code in required_codes:
        assert code in text


def test_whitepaper_draft_preserves_benchmark_and_reproduction_contracts() -> None:
    text = _doc_text()

    required_metrics = [
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
        "certificate_validity_rate",
    ]
    for metric in required_metrics:
        assert metric in text

    required_commands = [
        "python3 -m venv .venv",
        ". .venv/bin/activate",
        'python -m pip install -e ".[dev]"',
        "make check",
        "make test",
        "make demo",
    ]
    for command in required_commands:
        assert command in text

    assert "The demo does not require network access" in text


def test_whitepaper_draft_tracks_final_publication_gate_status() -> None:
    text = _doc_text()

    required_phrases = [
        "final paper gate started",
        "not final public publication",
        "public remote preflight validation",
        "GitHub Private Vulnerability Reporting configuration",
        "public release-note publication",
        "fresh-clone validation",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_whitepaper_draft_references_public_source_artifacts() -> None:
    text = _doc_text()

    required_sources = [
        "docs/FORMAL_MODEL_v0.2.md",
        "docs/CALIBRATION_METHODOLOGY_v0.1.md",
        "docs/REASON_CODES.md",
        "schemas/",
        "examples/",
        "docs/FASTGATE_DESIGN_v0.1.md",
        "docs/ARCANA_BENCH_v0.1.md",
        "docs/PUBLIC_INTEGRATION_CONTRACT_v0.1.md",
        "docs/LIMITATIONS_v0.1.md",
        "src/arcana/",
        "tests/",
    ]

    for source in required_sources:
        assert source in text


def test_whitepaper_draft_blocks_unsafe_claim_drift() -> None:
    text = _doc_text().lower()

    forbidden_phrases = [
        "certified" + " safe",
        "zero" + " risk",
        "perfect" + " sandbox",
        "objective safety" + " score",
        "risk was" + " eliminated",
        "arcana " + "pro" + "ves " + "safe",
    ]

    for phrase in forbidden_phrases:
        assert phrase not in text


def test_whitepaper_draft_has_no_private_boundary_tokens() -> None:
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
