from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "ARCANA_Whitepaper_v1.0_Manuscript.md"


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_whitepaper_v10_manuscript_sections_are_present() -> None:
    text = _doc_text()

    required_headings = [
        "# ARCANA: Model-Bounded Autonomy Accounting for Agentic Systems",
        "## Abstract",
        "## Contributions",
        "## Mathematical Propositions and Proof Sketches",
        "### Proposition 1 - Subcritical finite propagation",
        "### Proposition 2 - Upper-bound monotonicity",
        "### Proposition 3 - FastGate conservative bound",
        "### Negative Controls and Failure Fixtures",
        "## 19. Related Work",
        "## 22. Manuscript Status",
    ]

    for heading in required_headings:
        assert heading in text


def test_whitepaper_v10_manuscript_preserves_reviewed_claim_boundaries() -> None:
    text = _doc_text()

    required_phrases = [
        "final public manuscript; FWP-REVIEW-008 claim-language review passed",
        "not a production approval, enforcement approval, or commercial certificate authorization",
        "This manuscript does not claim production readiness, production enforcement, universal safety, or production certificate issuance.",
        "ARCANA estimates bounded autonomy under explicit risk model versions, calibration profiles, decision horizons, uncertainty bounds, and evidence assumptions.",
        "ARCANA is only as complete as the graph and evidence it is given.",
        "Admission-like decisions use `rho_upper`, not `rho_mean`.",
        "0 <= theta_rho <= 1",
        "K = unsafe propagation pressure",
        "L = impact or loss",
        "A0 artifacts are non-certifiable",
        "A1 remains `non_certifiable` and cannot support non-demo certificate-like",
        "`certifiable_under_profile` is a bounded public/reference semantic",
        "FastGate is not a weaker model",
        "artifact_contract_validity_rate",
        "ARCANA remains enforcement-neutral",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_whitepaper_v10_manuscript_tracks_publication_gate_state() -> None:
    text = _doc_text()

    required_phrases = [
        "Open FWP manuscript blockers:",
        "none.",
        "FWP-REVIEW-008 final public claim-language review has passed",
        "approved as the final public ARCANA manuscript artifact for the repository",
        "final manuscript transformation from draft to publication artifact",
        "final public claim-language review",
        "independent reproduction of local tests and deterministic demo",
    ]

    for phrase in required_phrases:
        assert phrase in text

    forbidden_stale_phrases = [
        "## 22. Draft Status",
        "Open review items:",
        "Open publication blocker:",
        "independent reproduction of local tests and demo;",
        "claim-language review pending",
        "not final publication until FWP-REVIEW-008 passes",
        "ready for final claim-language review, not final public publication",
        "final paper publication gate is still in progress",
    ]
    for phrase in forbidden_stale_phrases:
        assert phrase not in text


def test_whitepaper_v10_negative_controls_are_versioned() -> None:
    text = _doc_text()

    required_controls = [
        "scenario_type: negative_control",
        "`missing_decision_horizon`",
        "`graph_hash_mismatch`",
        "`a0_artifact_used_for_admission`",
        "`rho_mean_below_threshold_rho_upper_above_threshold`",
        "`fastgate_inconclusive`",
        "`loss_model_missing_required`",
        "`stale_evidence`",
    ]

    for control in required_controls:
        assert control in text


def test_whitepaper_v10_reproduction_commands_are_current() -> None:
    text = _doc_text()

    required_commands = [
        "python3 -m venv .venv",
        ". .venv/bin/activate",
        'python -m pip install -e ".[dev]"',
        "make check",
        "make test",
        "make demo",
        "The demo does not require network access.",
    ]

    for command in required_commands:
        assert command in text


def test_whitepaper_v10_blocks_unsafe_claim_drift() -> None:
    text = _doc_text().lower()

    forbidden_phrases = [
        "certified" + " safe",
        "zero" + " risk",
        "perfect" + " sandbox",
        "objective safety" + " score",
        "risk was" + " eliminated",
        "arcana " + "pro" + "ves " + "safe",
        "production" + " ready",
        "final public" + " publication is approved",
        "negative-control fixtures that prove",
    ]

    for phrase in forbidden_phrases:
        assert phrase not in text


def test_whitepaper_v10_has_no_private_boundary_tokens() -> None:
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
