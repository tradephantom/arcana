from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_MODULES = [
    "arcana",
    "arcana.model",
    "arcana.calibration",
    "arcana.matrices",
    "arcana.loss",
    "arcana.decision",
    "arcana.fastgate",
    "arcana.certificate",
    "arcana.schemas",
    "arcana.demo",
    "arcana.errors",
]
PRIVATE_TOKENS = [
    "".join(("cbe", "-", "context")),
    "".join(("provenance", "/")),
    "/".join(("docs", "canonical")),
    ".".join(("tradephantom", "internal")),
    "_".join(("CBE", "DENY", "")),
    "_".join(("CBE", "REQUIRE", "")),
]


def test_python_version_is_supported() -> None:
    assert sys.version_info >= (3, 11)


def test_package_modules_import() -> None:
    for module_name in PACKAGE_MODULES:
        module = importlib.import_module(module_name)
        assert module.__name__ == module_name


def test_pyproject_declares_planned_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = set(project["project"]["dependencies"])
    dev_dependencies = set(project["project"]["optional-dependencies"]["dev"])

    assert any(item.startswith("numpy") for item in dependencies)
    assert any(item.startswith("jsonschema") for item in dependencies)
    assert any(item.startswith("pytest") for item in dev_dependencies)


def test_scaffold_has_no_private_workspace_tokens() -> None:
    checked_paths = [
        *Path(ROOT / "src").rglob("*.py"),
        *Path(ROOT / "tests").rglob("*.py"),
        ROOT / "pyproject.toml",
    ]

    for path in checked_paths:
        text = path.read_text(encoding="utf-8")
        for token in PRIVATE_TOKENS:
            assert token not in text, f"{path.relative_to(ROOT)} contains {token}"
