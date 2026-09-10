from __future__ import annotations

import hashlib
import shutil

import pytest

from arcana import _resources
from arcana.bench_runner import build_input_manifest, run_public_benchmark, verify_benchmark_report_against_source
from arcana.errors import ArcanaValidationError
from arcana.schemas import ROOT


def test_source_resource_layout() -> None:
    assert _resources.resource_root(ROOT / "src" / "arcana") == ROOT


def test_installed_layout_does_not_search_cwd(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    package = tmp_path / "site-packages" / "arcana"
    assert _resources.resource_root(package) == package / "_data"


def test_source_layout_requires_project_metadata(tmp_path) -> None:
    package = tmp_path / "src" / "arcana"
    assert _resources.resource_root(package) == package / "_data"


@pytest.mark.parametrize("path", ["../secret", "/absolute", "src/../secret", "src\\arcana"])
def test_provenance_rejects_traversal(path) -> None:
    with pytest.raises(ArcanaValidationError) as caught:
        _resources.provenance_path(ROOT, path)
    assert caught.value.code == "package_provenance_path_invalid"


def test_installed_provenance_reads_executable_not_duplicate(tmp_path, monkeypatch) -> None:
    package = tmp_path / "arcana"
    monkeypatch.setattr(_resources, "PACKAGE_DIR", package)
    assert _resources.provenance_path(package / "_data", "src/arcana/_numerics.py") == package / "_numerics.py"
    assert _resources.provenance_path(package / "_data", "schemas/schema.json") == package / "_data/schemas/schema.json"
    assert _resources.provenance_path(tmp_path / "custom", "src/arcana/_numerics.py") == tmp_path / "custom/src/arcana/_numerics.py"


def test_manifest_covers_every_runtime_module() -> None:
    paths = {entry.path for entry in build_input_manifest()}
    modules = {path.relative_to(ROOT).as_posix() for path in (ROOT / "src/arcana").glob("*.py")}
    assert modules <= paths
    for entry in build_input_manifest():
        assert entry.sha256 == "sha256:" + hashlib.sha256((ROOT / entry.path).read_bytes()).hexdigest()


def test_source_numerical_tamper_invalidates_report(tmp_path) -> None:
    report = run_public_benchmark().to_mapping()
    shutil.copytree(ROOT / "examples", tmp_path / "examples")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    shutil.copytree(ROOT / "src", tmp_path / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    numerical = tmp_path / "src/arcana/_numerics.py"
    numerical.write_bytes(numerical.read_bytes() + b"\n# tamper\n")
    with pytest.raises(ArcanaValidationError) as caught:
        verify_benchmark_report_against_source(report, tmp_path)
    assert caught.value.code == "benchmark_report_source_manifest_mismatch"
