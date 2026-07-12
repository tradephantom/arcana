from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("arcana_public_audit", ROOT / "tools" / "audit_public.py")
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


def test_secret_bearing_suffixes_are_hard_denied() -> None:
    assert {".key", ".pem", ".p12", ".pfx"}.issubset(AUDIT.SECRET_SUFFIXES)


def test_private_key_marker_is_detected() -> None:
    marker = "-----BEGIN " + "PRIVATE KEY-----\n"
    findings = AUDIT.line_findings(ROOT / "README.md", marker)

    assert any(finding.code == "private_key_material" for finding in findings)


def test_credential_assignment_is_detected() -> None:
    name = "_".join(("client", "secret"))
    findings = AUDIT.line_findings(ROOT / "README.md", f"{name} = '0123456789abcdef0123456789abcdef'\n")

    assert any(finding.code == "credential_assignment" for finding in findings)
