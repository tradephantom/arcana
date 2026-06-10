from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = {
    "license": ROOT / "LICENSE.md",
    "contributing": ROOT / "CONTRIBUTING.md",
    "security": ROOT / "SECURITY.md",
    "limitations": ROOT / "docs" / "LIMITATIONS_v0.1.md",
}


def _read(name: str) -> str:
    return DOCS[name].read_text(encoding="utf-8")


def test_release_readiness_documents_exist() -> None:
    for path in DOCS.values():
        assert path.exists(), f"{path.relative_to(ROOT)} is missing"


def test_license_profile_is_final_and_file_scoped() -> None:
    text = _read("license")

    required_phrases = [
        "final public license profile v1.0",
        "Apache-2.0",
        "CC-BY-4.0",
        "Source code under `src/`, `tests/`, and `tools/`",
        "Public schemas under `schemas/`",
        "Synthetic examples under `examples/`",
        "Public documentation under `docs/`",
        "This final license profile removes the previous license-review blocker",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_contributing_policy_preserves_public_boundary_and_gates() -> None:
    text = _read("contributing")

    required_phrases = [
        "contribution intake is not open until public remote setup is complete",
        "Unknown provenance means risky",
        "Apache-2.0",
        "CC-BY-4.0",
        "make check",
        "make test",
        "make demo",
        "use explicit reason-code branches",
        "Distinct failure modes need distinct reason codes and tests",
        "public/private boundary",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_security_policy_covers_arcana_specific_failure_classes() -> None:
    text = _read("security")

    required_phrases = [
        "GitHub Private Vulnerability Reporting",
        "GitHub Security Advisories",
        "public-safe reproduction steps",
        "Schema bypass",
        "Reason-code collapse",
        "FastGate false admission",
        "Calibration overclaim",
        "Evidence mismatch",
        "Benchmark mislabeling",
        "make check",
        "make test",
        "make demo",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_limitations_document_keeps_arcana_model_bounded() -> None:
    text = _read("limitations")

    required_phrases = [
        "model version",
        "calibration profile",
        "decision horizon",
        "uncertainty bounds",
        "K = unsafe propagation pressure",
        "L = impact or loss",
        "A0 is demo-only and always non-certifiable",
        "FastGate is a conservative optimization path",
        "task success is not an ARCANA safety score",
        "Public integration guidance is enforcement-neutral",
        "final license profile must be present",
        "GitHub Private Vulnerability Reporting must be enabled",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_release_readiness_docs_have_no_private_boundary_tokens() -> None:
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

    for name in DOCS:
        text = _read(name)
        for token in forbidden_tokens:
            assert token not in text, f"{name} contains private token {token}"
