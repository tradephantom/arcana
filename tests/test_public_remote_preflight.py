from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "PUBLIC_REMOTE_PREFLIGHT_v0.1.md"


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_public_remote_preflight_sections_are_present() -> None:
    text = _doc_text()

    required_headings = [
        "# ARCANA Public Remote Preflight v0.1",
        "## 1. Hard Rule",
        "## 2. Required Local State",
        "## 3. Boundary Checks",
        "## 4. GitHub Cost Controls",
        "## 5. Remote Creation Sequence",
        "## 6. Post-Push Validation",
        "## 7. Stop Conditions",
        "## 9. Current Publication Status",
    ]

    for heading in required_headings:
        assert heading in text


def test_public_remote_preflight_requires_local_gates_and_manifest() -> None:
    text = _doc_text()

    required_phrases = [
        "git status --short",
        "git remote -v",
        "make check",
        "make test",
        "make demo",
        "python -m compileall -q src",
        "git diff --check",
        "PUBLIC_MANIFEST.md",
        "LICENSE.md",
        "SECURITY.md",
        "docs/LIMITATIONS_v0.1.md",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_public_remote_preflight_preserves_cost_controls_and_security_channel() -> None:
    text = _doc_text()

    required_phrases = [
        "GitHub Private Vulnerability Reporting",
        "no GitHub Actions by default",
        "no Git LFS",
        "no GitHub Packages",
        "no Codespaces",
        "no GitHub Pages",
        "no larger hosted runners",
        "no paid GitHub feature",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_public_remote_preflight_blocks_publication_on_boundary_failures() -> None:
    text = _doc_text()

    required_stop_conditions = [
        "public audit fails",
        "schema validation fails",
        "tests fail",
        "demo fails",
        "worktree is dirty",
        "manifest has unlisted files",
        "GitHub Private Vulnerability Reporting cannot be enabled",
        "paid feature is required",
        "private or sensitive material is discovered",
    ]

    for condition in required_stop_conditions:
        assert condition in text


def test_public_remote_preflight_has_no_private_boundary_tokens() -> None:
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
