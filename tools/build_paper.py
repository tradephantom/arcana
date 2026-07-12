#!/usr/bin/env python3
"""Reproducibly transform and compile the reviewed ARCANA manuscript."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CONTRACT = ROOT / "paper" / "SOURCE.json"
METADATA = ROOT / "paper" / "metadata.yaml"
HEADER = ROOT / "paper" / "header.tex"
BEFORE_BODY = ROOT / "paper" / "before-body.tex"
EXPECTED_SOURCE_KEYS = {
    "schema_version",
    "manuscript",
    "manuscript_sha256",
    "reviewed_public_commit",
    "reviewed_public_tree",
    "source_date_epoch",
    "toolchain",
    "paper_tex",
    "claim_boundary",
}
EXPECTED_TOOLCHAIN_KEYS = {"pandoc", "tectonic"}
FORBIDDEN_TEX_TOKENS = (
    "/".join(("", "Users", "")),
    "file" + "://",
    "FWP-REVIEW-",
    "AXCP Enterprise",
    "NEMORG",
    "CBE" + "_DENY_",
    "CBE" + "_REQUIRE_",
)


class PaperBuildError(RuntimeError):
    """A deterministic paper-build precondition failed."""


def _load_source_contract() -> dict[str, Any]:
    try:
        contract = json.loads(SOURCE_CONTRACT.read_text(encoding="ascii"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PaperBuildError(f"paper_source_contract_invalid: {exc}") from exc
    if not isinstance(contract, dict) or set(contract) != EXPECTED_SOURCE_KEYS:
        raise PaperBuildError("paper_source_contract_shape_invalid")
    if contract["schema_version"] != "arcana.paper_source.v0.1":
        raise PaperBuildError("paper_source_schema_unsupported")
    if contract["claim_boundary"] != "research_reference_only_no_production_authority":
        raise PaperBuildError("paper_claim_boundary_invalid")
    if not isinstance(contract["source_date_epoch"], int) or contract["source_date_epoch"] < 1:
        raise PaperBuildError("paper_source_date_epoch_invalid")
    for key in ("reviewed_public_commit", "reviewed_public_tree"):
        if not isinstance(contract[key], str) or re.fullmatch(r"[0-9a-f]{40}", contract[key]) is None:
            raise PaperBuildError(f"paper_{key}_invalid")
    toolchain = contract["toolchain"]
    if not isinstance(toolchain, dict) or set(toolchain) != EXPECTED_TOOLCHAIN_KEYS:
        raise PaperBuildError("paper_toolchain_shape_invalid")
    for name in sorted(EXPECTED_TOOLCHAIN_KEYS):
        version = toolchain[name]
        if not isinstance(version, str) or re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,2}", version) is None:
            raise PaperBuildError(f"paper_toolchain_version_invalid:{name}")
    return contract


def _resolve_relative_file(raw_path: Any, field: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
        raise PaperBuildError(f"paper_{field}_path_invalid")
    candidate = (ROOT / raw_path).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise PaperBuildError(f"paper_{field}_path_outside_root") from exc
    if not candidate.is_file():
        raise PaperBuildError(f"paper_{field}_missing")
    return candidate


def _verify_manuscript(contract: dict[str, Any]) -> Path:
    manuscript = _resolve_relative_file(contract["manuscript"], "manuscript")
    expected_hash = contract["manuscript_sha256"]
    if not isinstance(expected_hash, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", expected_hash) is None:
        raise PaperBuildError("paper_manuscript_hash_invalid")
    observed_hash = "sha256:" + hashlib.sha256(manuscript.read_bytes()).hexdigest()
    if observed_hash != expected_hash:
        raise PaperBuildError("paper_manuscript_hash_mismatch")
    return manuscript


def _prepare_markdown(manuscript: Path) -> str:
    text = manuscript.read_text(encoding="ascii")
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# ARCANA:"):
        raise PaperBuildError("paper_manuscript_title_missing")
    index = 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or not lines[index].startswith(">"):
        raise PaperBuildError("paper_manuscript_status_block_missing")
    while index < len(lines) and lines[index].startswith(">"):
        index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    prepared = "\n".join(lines[index:]).rstrip() + "\n"
    if not prepared.startswith("## Abstract\n"):
        raise PaperBuildError("paper_manuscript_abstract_missing")
    return prepared


def _tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise PaperBuildError(f"paper_tool_missing:{name}")
    return path


def _verified_tool(name: str, expected_version: str, env: dict[str, str]) -> str:
    path = _tool(name)
    try:
        result = subprocess.run(
            [path, "--version"],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PaperBuildError(f"paper_tool_version_unavailable:{name}") from exc
    lines = result.stdout.splitlines()
    if not lines:
        raise PaperBuildError(f"paper_tool_version_output_empty:{name}")
    prefix = "pandoc " if name == "pandoc" else "Tectonic "
    if lines[0].strip() != prefix + expected_version:
        raise PaperBuildError(f"paper_tool_version_mismatch:{name}")
    return path


def _run(command: list[str], env: dict[str, str]) -> None:
    try:
        subprocess.run(command, cwd=ROOT, env=env, check=True)
    except OSError as exc:
        raise PaperBuildError(f"paper_command_execution_failed:{Path(command[0]).name}") from exc
    except subprocess.CalledProcessError as exc:
        raise PaperBuildError(f"paper_command_failed:{Path(command[0]).name}:{exc.returncode}") from exc


def _transform_abstract(tex: str) -> str:
    abstract_marker = "\\section{Abstract}\\label{abstract}"
    next_section_marker = "\\section{1. Paper Rule}"
    start = tex.find(abstract_marker)
    end = tex.find(next_section_marker, start + len(abstract_marker))
    if start < 0 or end < 0:
        raise PaperBuildError("paper_abstract_transform_marker_missing")
    abstract = tex[start + len(abstract_marker) : end].strip()
    replacement = (
        "\\begin{abstract}\n"
        + abstract
        + "\n\\end{abstract}\n\n"
        + "\\clearpage\n\\tableofcontents\n\\clearpage\n\n"
    )
    return tex[:start] + replacement + tex[end:]


def _format_for_bounded_pages(tex: str) -> str:
    tex = tex.replace(
        "\\begin{verbatim}",
        "\\begin{Verbatim}[breaklines=true,breakanywhere=true,fontsize=\\small]",
    ).replace("\\end{verbatim}", "\\end{Verbatim}")
    tex = tex.replace(
        "\\begin{longtable}[]{@{}ll@{}}",
        "\\begin{longtable}[]{@{}>{\\raggedright\\arraybackslash}p{0.31\\linewidth}"
        ">{\\raggedright\\arraybackslash}p{0.62\\linewidth}@{}}",
    )
    tex = tex.replace(
        "\\begin{longtable}[]{@{}lll@{}}",
        "\\begin{longtable}[]{@{}>{\\raggedright\\arraybackslash}p{0.27\\linewidth}"
        ">{\\raggedright\\arraybackslash}p{0.17\\linewidth}"
        ">{\\raggedright\\arraybackslash}p{0.47\\linewidth}@{}}",
    )
    tex = tex.replace(
        "\\begin{longtable}[]{@{}llll@{}}",
        "\\begin{longtable}[]{@{}>{\\raggedright\\arraybackslash}p{0.07\\linewidth}"
        ">{\\raggedright\\arraybackslash}p{0.19\\linewidth}"
        ">{\\raggedright\\arraybackslash}p{0.34\\linewidth}"
        ">{\\raggedright\\arraybackslash}p{0.27\\linewidth}@{}}",
    )

    simple_texttt = re.compile(r"\\texttt\{((?:[A-Za-z0-9./:+()=-]|\\_)+)\}")

    def replace_long_identifier(match: re.Match[str]) -> str:
        display = match.group(1).replace("\\_", "_")
        if "\\_" not in match.group(1) and "/" not in display and len(display) < 24:
            return match.group(0)
        return f"\\path{{{display}}}"

    return simple_texttt.sub(replace_long_identifier, tex)


def _validate_tex(tex_bytes: bytes) -> None:
    try:
        tex = tex_bytes.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PaperBuildError("paper_tex_non_ascii") from exc
    required = (
        "\\begin{abstract}",
        "\\tableofcontents",
        "\\section{1. Paper Rule}",
        "\\section{18. Limitations}",
        "\\section{22. Conclusion}",
        "research/reference",
        "not a production approval",
    )
    for marker in required:
        if marker not in tex:
            raise PaperBuildError(f"paper_tex_required_marker_missing:{marker}")
    for token in FORBIDDEN_TEX_TOKENS:
        if token in tex:
            raise PaperBuildError(f"paper_tex_forbidden_token:{token}")


def _generate_tex(manuscript: Path, pandoc: str, env: dict[str, str]) -> bytes:
    with tempfile.TemporaryDirectory(prefix="arcana-paper-") as temp_dir:
        temp_root = Path(temp_dir)
        prepared = temp_root / "manuscript.md"
        generated = temp_root / "paper.tex"
        prepared.write_text(_prepare_markdown(manuscript), encoding="ascii")
        _run(
            [
                pandoc,
                str(prepared),
                "--from=gfm+tex_math_dollars",
                "--to=latex",
                "--standalone",
                "--top-level-division=section",
                "--shift-heading-level-by=-1",
                "--syntax-highlighting=none",
                "--wrap=auto",
                "--columns=88",
                f"--metadata-file={METADATA}",
                f"--include-in-header={HEADER}",
                f"--include-before-body={BEFORE_BODY}",
                f"--output={generated}",
            ],
            env,
        )
        transformed = _format_for_bounded_pages(
            _transform_abstract(generated.read_text(encoding="ascii"))
        )
        tex_bytes = transformed.encode("ascii")
    _validate_tex(tex_bytes)
    return tex_bytes


def _validated_pdf_outputs(output_dir: Path, tex_path: Path) -> tuple[bytes, bytes]:
    pdf_path = output_dir / f"{tex_path.stem}.pdf"
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise PaperBuildError("paper_pdf_missing")
    log_path = output_dir / f"{tex_path.stem}.log"
    if not log_path.is_file():
        raise PaperBuildError("paper_pdf_log_missing")
    log_bytes = log_path.read_bytes()
    log_text = log_bytes.decode("utf-8", errors="replace").lower()
    fatal_layout_markers = (
        "overfull \\hbox",
        "annotation out of page boundary",
        "undefined references",
        "missing character",
    )
    for marker in fatal_layout_markers:
        if marker in log_text:
            reason = marker.replace(" ", "_").replace("\\", "")
            raise PaperBuildError(f"paper_pdf_layout_warning:{reason}")
    return pdf_path.read_bytes(), log_bytes


def _compile_pdf(tex_path: Path, tectonic: str, env: dict[str, str]) -> Path:
    output_dir = ROOT / "build" / "paper"
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="arcana-paper-pdf-") as temp_dir:
        temp_output = Path(temp_dir)
        _run(
            [tectonic, "--keep-logs", "--outdir", str(temp_output), str(tex_path)],
            env,
        )
        pdf_bytes, log_bytes = _validated_pdf_outputs(temp_output, tex_path)
    pdf_path = output_dir / f"{tex_path.stem}.pdf"
    log_path = output_dir / f"{tex_path.stem}.log"
    _write_atomic(pdf_path, pdf_bytes)
    _write_atomic(log_path, log_bytes)
    return pdf_path


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        os.fchmod(handle.fileno(), 0o644)
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare generated TeX with the checked-in artifact")
    mode.add_argument("--pdf", action="store_true", help="generate TeX and compile the PDF under build/paper")
    args = parser.parse_args()

    try:
        contract = _load_source_contract()
        manuscript = _verify_manuscript(contract)
        tex_path = (ROOT / contract["paper_tex"]).resolve()
        if tex_path.parent != (ROOT / "paper").resolve():
            raise PaperBuildError("paper_tex_path_invalid")
        env = dict(os.environ)
        env["SOURCE_DATE_EPOCH"] = str(contract["source_date_epoch"])
        pandoc = _verified_tool("pandoc", contract["toolchain"]["pandoc"], env)
        generated = _generate_tex(manuscript, pandoc, env)
        if args.check:
            if not tex_path.is_file() or tex_path.read_bytes() != generated:
                raise PaperBuildError("paper_tex_reproduction_mismatch")
            print("paper tex check: PASS")
            return 0
        _write_atomic(tex_path, generated)
        print(f"paper tex generated: {tex_path.relative_to(ROOT)}")
        if args.pdf:
            tectonic = _verified_tool(
                "tectonic", contract["toolchain"]["tectonic"], env
            )
            pdf_path = _compile_pdf(tex_path, tectonic, env)
            print(f"paper pdf generated: {pdf_path.relative_to(ROOT)}")
        return 0
    except PaperBuildError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
