from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "ARCANA_Whitepaper_v0.2_Outline.md"


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_whitepaper_outline_sections_are_present() -> None:
    text = _doc_text()

    required_headings = [
        "# ARCANA Whitepaper / Paper v0.2 Outline",
        "## 1. Paper Rule",
        "## 4. Claimed Contributions",
        "### 5.4 Formal Model",
        "### 5.5 Calibration Methodology and Limitations",
        "### 5.8 FastGate",
        "### 5.9 ARCANA-Bench",
        "### 5.10 Reference Implementation Reproduction",
        "### 5.12 Limitations and Non-Goals",
        "## 6. Evidence Table for v0.2",
        "## 8. Publication Readiness Gate",
        "## 9. Reviewer Checklist",
    ]

    for heading in required_headings:
        assert heading in text


def test_whitepaper_outline_references_public_source_artifacts() -> None:
    text = _doc_text()

    required_sources = [
        "docs/FORMAL_MODEL_v0.2.md",
        "docs/CALIBRATION_METHODOLOGY_v0.1.md",
        "docs/REASON_CODES.md",
        "docs/FASTGATE_DESIGN_v0.1.md",
        "docs/ARCANA_BENCH_v0.1.md",
        "docs/PUBLIC_INTEGRATION_CONTRACT_v0.1.md",
        "src/arcana/",
        "tests/",
        "schemas/",
        "examples/benchmark_*.synthetic.json",
    ]

    for source in required_sources:
        assert source in text


def test_whitepaper_outline_keeps_claims_model_bounded() -> None:
    text = _doc_text()

    required_boundaries = [
        "model-bounded autonomy accounting",
        "A0 outputs are non-certifiable",
        "Calibration uncertainty is a first-class limitation",
        "K describes unsafe propagation pressure; L describes impact",
        "benchmark task success is not an ARCANA safety score",
        "FastGate is an optimization path",
        "integration guidance remains enforcement-neutral",
    ]

    for boundary in required_boundaries:
        assert boundary in text

    forbidden_phrases = [
        "certified" + " safe",
        "zero" + " risk",
        "perfect" + " sandbox",
        "objective safety" + " score",
        "risk was" + " eliminated",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in text.lower()


def test_whitepaper_outline_preserves_reproduction_gate() -> None:
    text = _doc_text()

    required_commands = [
        "python3 -m venv .venv",
        '. .venv/bin/activate',
        'python -m pip install -e ".[dev]"',
        "make check",
        "make test",
        "make demo",
    ]

    for command in required_commands:
        assert command in text

    assert "public-boundary audit is part of the gate" in text
    assert "no network dependency is required for the demo" in text


def test_whitepaper_outline_requires_benchmark_metric_separation() -> None:
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

    required_scenario_classes = [
        "indirect prompt injection containment",
        "persistent memory poisoning containment",
        "tool misuse scope reduction",
        "unsafe delegation cascade",
        "benchmark gaming detection",
        "dynamic execution risk",
    ]

    for scenario_class in required_scenario_classes:
        assert scenario_class in text


def test_whitepaper_outline_has_no_private_boundary_tokens() -> None:
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
