from __future__ import annotations

import json
import tomllib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DOI = "10.5281/zenodo.21333463"
AUTHOR = "Julio Elizondo Rodriguez"
AFFILIATION = "TradePhantom LLC"
EMAIL = "dev@tradephantom.com"


def _publication() -> dict[str, object]:
    return json.loads(
        (ROOT / "paper" / "PUBLICATION.json").read_text(encoding="ascii")
    )


def _citation() -> dict[str, object]:
    loaded = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="ascii"))
    assert isinstance(loaded, dict)
    return loaded


def test_publication_contract_has_exact_identity_and_claim_boundary() -> None:
    publication = _publication()

    assert publication["schema_version"] == "arcana.paper_publication.v0.1"
    assert publication["title"] == (
        "ARCANA: Autonomy Risk Calculus for Agentic Network Assurance"
    )
    assert publication["subtitle"] == (
        "Model-Bounded Autonomy Accounting for Agentic Systems"
    )
    assert publication["version"] == "1.0"
    assert publication["publication_type"] == "preprint"
    assert publication["publication_date"] == "2026-07-13"
    assert publication["doi"] == DOI
    assert publication["publisher"] == "Zenodo"
    assert publication["license"] == "CC-BY-4.0"
    assert publication["review_status"] == "not_externally_peer_reviewed"
    assert publication["evidence_scope"] == (
        "deterministic_synthetic_reference_only"
    )
    assert publication["claim_boundary"] == (
        "research_reference_only_no_production_authority"
    )

    assert publication["authors"] == [
        {
            "family_name": "Elizondo Rodriguez",
            "given_name": "Julio",
            "display_name": AUTHOR,
            "affiliation": AFFILIATION,
            "email": EMAIL,
        }
    ]


def test_citation_file_separates_software_and_preprint_metadata() -> None:
    citation = _citation()

    assert citation["cff-version"] == "1.2.0"
    assert citation["type"] == "software"
    assert citation["title"] == (
        "ARCANA - Autonomy Risk Calculus for Agentic Network Assurance"
    )
    assert citation["version"] == "0.1.1"
    assert citation["license"] == "Apache-2.0"
    assert citation["repository-code"] == "https://github.com/tradephantom/arcana"
    assert citation["authors"] == [
        {
            "family-names": "Elizondo Rodriguez",
            "given-names": "Julio",
            "affiliation": AFFILIATION,
            "email": EMAIL,
        }
    ]

    preferred = citation["preferred-citation"]
    assert isinstance(preferred, dict)
    assert preferred["type"] == "article"
    assert preferred["title"] == (
        "ARCANA: Autonomy Risk Calculus for Agentic Network Assurance"
    )
    assert preferred["doi"] == DOI
    assert preferred["version"] == "1.0"
    assert preferred["publisher"] == {"name": "Zenodo"}


def test_publication_identity_is_consistent_across_public_artifacts() -> None:
    paths = [
        ROOT / "README.md",
        ROOT / "docs" / "ARCANA_Roadmap_v0.1_Public.md",
        ROOT / "docs" / "ARCANA_Whitepaper_v1.0_Manuscript.md",
        ROOT / "docs" / "PUBLIC_RELEASE_NOTES_v0.1.1.md",
        ROOT / "paper" / "metadata.yaml",
        ROOT / "paper" / "header.tex",
        ROOT / "paper" / "ARCANA_Whitepaper_v1.0.tex",
    ]
    for path in paths:
        text = path.read_text(encoding="ascii")
        assert DOI in text, path

    for path in [
        ROOT / "docs" / "ARCANA_Whitepaper_v1.0_Manuscript.md",
        ROOT / "paper" / "metadata.yaml",
        ROOT / "paper" / "ARCANA_Whitepaper_v1.0.tex",
    ]:
        assert AUTHOR in path.read_text(encoding="ascii"), path

    header = (ROOT / "paper" / "header.tex").read_text(encoding="ascii")
    assert AFFILIATION in header
    assert EMAIL in header
    assert "https://getaxcp.com" in header


def test_python_project_metadata_matches_software_release() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="ascii"))[
        "project"
    ]

    assert project["version"] == "0.1.1"
    assert project["license"] == {"text": "Apache-2.0"}
    assert project["authors"] == [{"name": AUTHOR, "email": EMAIL}]
    assert project["urls"] == {
        "Homepage": "https://getaxcp.com",
        "Repository": "https://github.com/tradephantom/arcana",
        "Paper": f"https://doi.org/{DOI}",
    }

    package_init = (ROOT / "src" / "arcana" / "__init__.py").read_text(
        encoding="ascii"
    )
    assert '__version__ = "0.1.1"' in package_init


def test_publication_metadata_has_no_unresolved_placeholder() -> None:
    publication_paths = [
        ROOT / "CITATION.cff",
        ROOT / "README.md",
        ROOT / "docs" / "PUBLIC_RELEASE_NOTES_v0.1.1.md",
        ROOT / "paper" / "PUBLICATION.json",
        ROOT / "paper" / "metadata.yaml",
        ROOT / "paper" / "header.tex",
        ROOT / "paper" / "ARCANA_Whitepaper_v1.0.tex",
    ]
    forbidden = ("DOI_PENDING", "PLACEHOLDER", "TBD", "TO_BE_ASSIGNED")
    for path in publication_paths:
        text = path.read_text(encoding="ascii")
        for token in forbidden:
            assert token not in text, (path, token)
