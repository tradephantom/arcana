from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "ARCANA_Whitepaper_v0.3_Draft.md"


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_whitepaper_v03_sections_are_present() -> None:
    text = _doc_text()

    required_headings = [
        "# ARCANA: Model-Bounded Autonomy Accounting for Agentic Systems",
        "## Contributions",
        "## Mathematical Propositions and Proof Sketches",
        "### Proposition 1 - Subcritical finite propagation",
        "### Proposition 2 - Upper-bound monotonicity",
        "### Proposition 3 - FastGate conservative bound",
        "### Negative Controls and Failure Fixtures",
        "## 19. Related Work",
        "## 22. Draft Status",
    ]

    for heading in required_headings:
        assert heading in text


def test_whitepaper_v03_preserves_superbrain_review_hardening_points() -> None:
    text = _doc_text()

    required_phrases = [
        "ARCANA is only as complete as the graph and evidence it is given.",
        "Calibration profiles must prevent double-counting between `exposure_e`,",
        "`certifiable_under_profile` is a bounded public/reference semantic",
        "artifact_contract_validity_rate",
        "Earlier drafts used the name `certificate_validity_rate`",
        "ARCANA can be integrated with capability-bound execution systems",
        "The draft remains ready for staged expert review, not final public publication.",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_whitepaper_v03_related_work_links_are_public() -> None:
    text = _doc_text()

    required_links = [
        "https://modelcontextprotocol.io/docs/getting-started/intro",
        "https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/",
        "https://www.nist.gov/itl/ai-risk-management-framework",
    ]

    for link in required_links:
        assert link in text


def test_whitepaper_v03_negative_controls_are_specific() -> None:
    text = _doc_text()

    required_controls = [
        "Missing decision horizon",
        "Graph hash mismatch",
        "A0 artifact used for admission",
        "`rho_mean` below threshold but `rho_upper` above threshold",
        "FastGate inconclusive",
        "Loss model missing while loss is required",
        "Stale evidence",
    ]

    for control in required_controls:
        assert control in text


def test_whitepaper_v03_blocks_unsafe_claim_drift() -> None:
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
