from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tools import build_paper


ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = ROOT / "paper"
SOURCE_CONTRACT = PAPER_ROOT / "SOURCE.json"
PUBLICATION_CONTRACT = PAPER_ROOT / "PUBLICATION.json"
TEX_PATH = PAPER_ROOT / "ARCANA_Whitepaper_v1.0.tex"


def _source_contract() -> dict[str, object]:
    return json.loads(SOURCE_CONTRACT.read_text(encoding="ascii"))


def test_paper_source_contract_binds_reviewed_manuscript() -> None:
    contract = _source_contract()
    manuscript = ROOT / str(contract["manuscript"])
    publication = ROOT / str(contract["publication"])
    observed_manuscript = "sha256:" + hashlib.sha256(manuscript.read_bytes()).hexdigest()
    observed_publication = "sha256:" + hashlib.sha256(publication.read_bytes()).hexdigest()

    assert contract["schema_version"] == "arcana.paper_source.v0.2"
    assert contract["claim_boundary"] == "research_reference_only_no_production_authority"
    assert observed_manuscript == contract["manuscript_sha256"]
    assert observed_publication == contract["publication_sha256"]
    assert contract["publication"] == "paper/PUBLICATION.json"
    publication_contract = json.loads(publication.read_text(encoding="ascii"))
    assert datetime.fromtimestamp(contract["source_date_epoch"], tz=UTC).date().isoformat() == (
        publication_contract["publication_date"]
    )
    assert contract["paper_tex"] == "paper/ARCANA_Whitepaper_v1.0.tex"
    assert contract["toolchain"] == {"pandoc": "3.10", "tectonic": "0.16.9"}


def test_latex_paper_preserves_public_claim_boundary() -> None:
    text = TEX_PATH.read_text(encoding="ascii")
    lower_text = text.lower()

    required = [
        "public research manuscript v1.0",
        "not a production approval",
        "not a production approval, enforcement approval",
        "research/reference",
        "\\begin{abstract}",
        "\\tableofcontents",
        "\\section{18. Limitations}",
        "\\section{22. Conclusion}",
        "\\section{23. References}",
        "10.5281/zenodo.21333463",
        "Julio Elizondo Rodriguez",
        "TradePhantom LLC",
        "CC BY 4.0",
    ]
    for phrase in required:
        assert phrase.lower() in lower_text

    forbidden = [
        "/".join(("", "Users", "")),
        "file" + "://",
        "FWP-REVIEW-",
        "AXCP Enterprise",
        "NEMORG",
        "CBE" + "_DENY_",
        "CBE" + "_REQUIRE_",
        "proves agentic systems are safe",
        "production ready",
    ]
    for phrase in forbidden:
        assert phrase.lower() not in lower_text


def test_paper_build_inputs_are_ascii_and_public_safe() -> None:
    for path in [
        PAPER_ROOT / "SOURCE.json",
        PUBLICATION_CONTRACT,
        PAPER_ROOT / "metadata.yaml",
        PAPER_ROOT / "header.tex",
        PAPER_ROOT / "before-body.tex",
        PAPER_ROOT / "README.md",
        ROOT / "tools" / "build_paper.py",
    ]:
        path.read_text(encoding="ascii")


def test_paper_tool_version_mismatch_has_specific_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_paper, "_tool", lambda _name: "/usr/local/bin/pandoc")
    monkeypatch.setattr(
        build_paper.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["pandoc", "--version"], returncode=0, stdout="pandoc 3.9\n"
        ),
    )

    with pytest.raises(
        build_paper.PaperBuildError,
        match=r"^paper_tool_version_mismatch:pandoc$",
    ):
        build_paper._verified_tool("pandoc", "3.10", {})


def test_paper_pdf_validation_distinguishes_missing_and_layout_failure(tmp_path: Path) -> None:
    tex_path = tmp_path / "paper.tex"
    with pytest.raises(build_paper.PaperBuildError, match=r"^paper_pdf_missing$"):
        build_paper._validated_pdf_outputs(tmp_path, tex_path)

    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.7\n")
    with pytest.raises(build_paper.PaperBuildError, match=r"^paper_pdf_log_missing$"):
        build_paper._validated_pdf_outputs(tmp_path, tex_path)

    (tmp_path / "paper.log").write_text("Overfull \\hbox", encoding="ascii")
    with pytest.raises(
        build_paper.PaperBuildError,
        match=r"^paper_pdf_layout_warning:overfull_hbox$",
    ):
        build_paper._validated_pdf_outputs(tmp_path, tex_path)
