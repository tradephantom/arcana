from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DOCS = [
    ROOT / "README.md",
    ROOT / "PUBLIC_MANIFEST.md",
    ROOT / "docs" / "README.md",
    ROOT / "docs" / "ARCANA_PRD_v0.2_Public.md",
    ROOT / "docs" / "ARCANA_Roadmap_v0.1_Public.md",
    ROOT / "docs" / "ARCANA_Whitepaper_v1.0_Manuscript.md",
]


def _combined_public_claim_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC_DOCS)


def test_post_hardening_claim_language_is_consistent() -> None:
    text = _combined_public_claim_text()

    required_phrases = [
        "public research manuscript v1.0, post-hardening repository edition",
        "final public claim-language review is closed for the v1.0 manuscript",
        "final public claim-language review is closed for the repository manuscript",
        "venue-specific paper packaging remains separate from technical claim approval",
        "empirical_public_benchmark",
        "synthetic ARCANA-Bench",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_final_claim_language_blocks_pending_review_drift() -> None:
    text = _combined_public_claim_text().lower()

    forbidden_phrases = [
        "fwp-review-008 claim-language review pending",
        "not final publication until fwp-review-008 passes",
        "final public claim-language review remains open",
        "final paper gate still open pending final public claim-language review",
        "manuscript candidate pending final claim-language review",
        "ready for final claim-language review, not final public publication",
        "final paper publication gate is still in progress",
    ]

    for phrase in forbidden_phrases:
        assert phrase not in text


def test_public_certificate_language_uses_bounded_artifact_terms() -> None:
    text = _combined_public_claim_text().lower()

    forbidden_phrases = [
        "estimates and certifies bounded autonomy",
        "may issue bounded autonomy certificates",
        "produce bounded autonomy certificates",
        "may generate bounded autonomy certificates",
        "do not issue bounded autonomy certificates",
    ]

    for phrase in forbidden_phrases:
        assert phrase not in text

    assert "certificate-like bounded artifacts" in text
    assert "preferred public claim does not use `certifies bounded autonomy`" in text


def test_final_claim_language_preserves_public_non_goals() -> None:
    text = " ".join(_combined_public_claim_text().lower().split())

    required_phrases = [
        "does not prove that an agent or system is safe",
        "no production implementation is present",
        "production certificate issuance",
        "not a production approval, enforcement approval, or commercial certificate authorization",
        "not real-world safety, empirical calibration quality, production enforcement",
        "any latex, pdf, archive, or venue-specific derivative",
        "must preserve this claim boundary and the public/private product separation",
    ]

    for phrase in required_phrases:
        assert phrase in text
