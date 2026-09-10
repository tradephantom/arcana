"""Filesystem resources for source checkouts and ordinary wheel installations."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path, PurePosixPath

from arcana._validation import fail
from arcana.errors import ReasonCode


def resource_root(package_dir: Path) -> Path:
    # Only the explicit src layout can use checkout data; never search cwd.
    source_root = package_dir.parent.parent
    if package_dir.parent.name == "src" and (source_root / "pyproject.toml").is_file():
        return source_root
    return package_dir / "_data"


_package = files("arcana")
if not isinstance(_package, Path):
    fail(
        "package_resource_loader_unsupported",
        ReasonCode.DENY_MODEL_INPUT_INVALID,
        "ARCANA requires a filesystem installation; install its wheel with pip",
        ("resources",),
    )
PACKAGE_DIR = _package
RESOURCE_ROOT = resource_root(PACKAGE_DIR)


def provenance_path(root: Path, relative_path: str) -> Path:
    """Keep report identities stable while hashing installed executable source."""
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts or "\\" in relative_path:
        fail(
            "package_provenance_path_invalid",
            ReasonCode.DENY_MODEL_INPUT_INVALID,
            "provenance paths must be relative POSIX paths without traversal",
            ("input_manifest", relative_path),
        )
    if root == PACKAGE_DIR / "_data" and relative.parts[:2] == ("src", "arcana"):
        return PACKAGE_DIR.joinpath(*relative.parts[2:])
    return root.joinpath(*relative.parts)
