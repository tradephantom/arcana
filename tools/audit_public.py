#!/usr/bin/env python3
"""Audit the ARCANA public repository for release-boundary violations."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "PUBLIC_MANIFEST.md"

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
}

BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".docx",
    ".zip",
    ".tar",
    ".gz",
    ".mp4",
    ".m4a",
}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    code: str
    detail: str


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return sorted(files)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.relative_to(ROOT)} is not valid UTF-8") from exc


def load_manifest_paths() -> set[str]:
    text = read_text(MANIFEST)
    paths: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"\|\s*`([^`]+)`\s*\|", line)
        if match:
            paths.add(match.group(1))
    return paths


def is_ascii(text: str) -> bool:
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


def line_findings(path: Path, text: str) -> list[Finding]:
    rel = path.relative_to(ROOT)
    findings: list[Finding] = []

    deny_patterns: list[tuple[str, re.Pattern[str], str]] = [
        ("local_path", re.compile(r"/Users/|file://|/Volumes/"), "local filesystem path"),
        ("internal_schema_id", re.compile(r"tradephantom\.internal", re.I), "internal schema namespace"),
        ("adapter_reason_code", re.compile(r"\bCBE_(DENY|REQUIRE)_[A-Z0-9_]+\b"), "adapter-specific reason code"),
        ("private_source_tree", re.compile(r"docs/(canonical|cbe-context|research-seeds)|provenance/|AGENTS\.md"), "private workspace path"),
        ("private_code_path", re.compile(r"\binternal/[A-Za-z0-9_/.-]+"), "private implementation path"),
        ("private_mechanics", re.compile(r"\b(runtime broker implementation|concrete grant|COP admission parser)\b", re.I), "private implementation mechanics"),
        ("unsafe_positive_claim", re.compile(r"\b(certified safe|zero risk|perfect sandbox|objective safety score|eliminates agentic risk)\b", re.I), "unsafe public claim"),
        ("public_proves_safe_claim", re.compile(r"\bARCANA\s+proves\b.*\bsafe\b", re.I), "absolute safety claim"),
    ]

    for line_no, line in enumerate(text.splitlines(), start=1):
        for code, pattern, detail in deny_patterns:
            if pattern.search(line):
                findings.append(Finding(rel, line_no, code, detail))

    return findings


def audit_manifest(files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    manifest_paths = load_manifest_paths()
    actual_paths = {
        str(path.relative_to(ROOT))
        for path in files
        if ".git" not in path.relative_to(ROOT).parts
    }

    missing = sorted(manifest_paths - actual_paths)
    extra = sorted(actual_paths - manifest_paths)

    for path in missing:
        findings.append(Finding(MANIFEST.relative_to(ROOT), 0, "manifest_missing_file", f"{path} listed but not found"))

    for path in extra:
        findings.append(Finding(Path(path), 0, "manifest_unlisted_file", "file is not listed in PUBLIC_MANIFEST.md"))

    return findings


def audit() -> list[Finding]:
    files = iter_files()
    findings = audit_manifest(files)

    for path in files:
        rel = path.relative_to(ROOT)
        if path.suffix.lower() in BINARY_SUFFIXES:
            findings.append(Finding(rel, 0, "binary_artifact", "binary files are not allowed in the initial public tree"))
            continue
        try:
            text = read_text(path)
        except ValueError as exc:
            findings.append(Finding(rel, 0, "utf8_decode", str(exc)))
            continue
        if not is_ascii(text):
            findings.append(Finding(rel, 0, "non_ascii", "file must be ASCII for the initial public tree"))
        if rel != Path("tools/audit_public.py"):
            findings.extend(line_findings(path, text))

    return findings


def main() -> int:
    findings = audit()
    if not findings:
        print("public audit: PASS")
        return 0

    print("public audit: FAIL")
    for finding in findings:
        line = f":{finding.line}" if finding.line else ""
        print(f"- {finding.path}{line} [{finding.code}] {finding.detail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
