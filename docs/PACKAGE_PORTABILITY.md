# Installed Package Contract

Status: unreleased R2 correction, 2026-09-10.

## Supported Layouts

ARCANA supports editable/source checkouts with the explicit `src/arcana`
layout and ordinary pip-installed wheels on a filesystem. Direct zip imports
are not supported and report `package_resource_loader_unsupported`.
No resource lookup searches the current working directory or fetches a remote
schema. A missing installed data directory does not fall back to a checkout.

The canonical `schemas/` and `examples/` directories and build metadata are
included under `arcana/_data/` during wheel construction. They are not manually
duplicated in source control. Distribution mapping uses Hatch's documented
[forced inclusion](https://hatch.pypa.io/latest/config/build/#forced-inclusion).

`schemas.ROOT`, `SCHEMA_DIR` and `EXAMPLE_DIR` retain Path-based compatibility.
In an installed wheel, ROOT identifies the packaged data root, not a repository
or a writable output directory. Code requiring a checkout must use its own
explicit checkout path. Custom benchmark roots continue to describe source
trees with `src/arcana`, `schemas`, `examples` and `pyproject.toml`.

## Provenance

Benchmark manifest identities remain repository-relative POSIX names. For an
installed wheel, `src/arcana/*.py` resolves to the actual installed modules,
not to a bundled duplicate of their source. Missing files, symlinks, non-regular
files and read failures retain distinct benchmark validation issues.
Traversal is rejected with `package_provenance_path_invalid`.

The manifest now includes every runtime Python module, including `_numerics.py`
and FastGate. A regression test fails if a new module is omitted. This corrects
an incomplete earlier input manifest; report hashes change intentionally.
These hashes detect content differences relative to a trusted report, not
malicious substitution of both a report and its verifier. They are not signed
supply-chain attestations or a mathematical proof about deployed systems.

## Acceptance Gate

Run `make package-check` after installing `.[dev]`. This requires access to
the configured Python package index for isolated build and install dependencies.
The gate:

- builds a direct wheel and an sdist followed by a wheel from that sdist;
- compares every wheel member across the two build routes;
- installs each wheel in a separate venv without system-site packages;
- removes inherited PYTHONPATH/PYTHONHOME and uses an unrelated working folder;
- pins install dependencies to the locally tested environment;
- verifies installed import/resource locations, all schema definitions, every
  public typed example and byte-for-byte resource contents;
- compares demo and benchmark bytes with the source checkout at two hash seeds;
- verifies source reports against installed code and installed reports against source;
- modifies the installed numerical module and requires report verification to fail;
- writes the run receipt, candidate wheel hashes and report hash to
  `build/package-check.json`.

CI runs the same gate on Python 3.11 and 3.14 for current revisions. Historical
v0.1.0 replay intentionally retains its original gates and cannot establish R2
portability. Local success does not imply a hosted run has occurred.
