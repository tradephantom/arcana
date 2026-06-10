# ARCANA License

> Status: final public license profile v1.0
> Decision date: 2026-06-10
> Scope: ARCANA public release-candidate repository
> Remote gate: public remote publication still requires the remote preflight checklist and GitHub Private Vulnerability Reporting.

ARCANA uses a file-scope license profile.

## 1. License Profile

Unless a file states otherwise, this repository uses:

| Material | License | SPDX identifier |
| --- | --- | --- |
| Source code under `src/`, `tests/`, and `tools/` | Apache License 2.0 | `Apache-2.0` |
| Build and development files, including `Makefile`, `pyproject.toml`, and `.gitignore` | Apache License 2.0 | `Apache-2.0` |
| Public schemas under `schemas/` | Apache License 2.0 | `Apache-2.0` |
| Synthetic examples under `examples/` | Apache License 2.0 | `Apache-2.0` |
| Public documentation under `docs/` | Creative Commons Attribution 4.0 International | `CC-BY-4.0` |
| Top-level public documentation, including `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, and `PUBLIC_MANIFEST.md` | Creative Commons Attribution 4.0 International | `CC-BY-4.0` |

Repository-level SPDX summary:

```text
Apache-2.0 for code, schemas, examples, build files, and validation tooling.
CC-BY-4.0 for public documentation.
```

## 2. Apache-2.0 Scope

The Apache License 2.0 applies to:

- reference implementation source code;
- tests;
- validation and audit tools;
- build and packaging metadata;
- public JSON schemas;
- synthetic JSON fixtures and examples.

Use of Apache-2.0 is intended to make ARCANA's public reference implementation and machine-readable contracts practical for research and independent implementations.

The canonical Apache License 2.0 text is available from the Apache Software Foundation:

```text
https://www.apache.org/licenses/LICENSE-2.0
```

## 3. CC-BY-4.0 Scope

Creative Commons Attribution 4.0 International applies to:

- public product and roadmap documents;
- formal model documentation;
- calibration methodology;
- reason-code registry;
- FastGate design;
- benchmark documentation;
- integration contract;
- whitepaper/paper drafts;
- limitations and release-readiness documents.

Attribution should identify ARCANA and preserve the public claim boundary. Reuse must not imply that ARCANA proves safety, provides production enforcement, or issues production certificates.

The canonical CC-BY-4.0 legal code is available from Creative Commons:

```text
https://creativecommons.org/licenses/by/4.0/legalcode
```

## 4. No Private Material Grant

This license profile applies only to files intentionally included in this public release-candidate repository.

No license in this repository applies to:

- private operational implementations;
- customer data;
- private telemetry;
- private policy profiles;
- non-public calibration profiles;
- private evidence payloads;
- private lab or enterprise integration material;
- trademarks, names, or branding not explicitly included in this public release.

## 5. Contribution Compatibility

Contributions must be compatible with this license profile:

- code, schemas, examples, build files, tests, and tooling must be compatible with Apache-2.0;
- documentation must be compatible with CC-BY-4.0;
- no contribution may include private, restricted, customer, or non-public material.

External contribution intake still requires maintainer approval and the security channel described in `SECURITY.md`.

## 6. Remote Publication Gate

This final license profile removes the previous license-review blocker.

Public remote publication still requires:

- `make check`, `make test`, and `make demo` passing locally;
- all public files listed in `PUBLIC_MANIFEST.md`;
- public-boundary audit passing;
- GitHub Private Vulnerability Reporting enabled on the public remote before announcement;
- no paid GitHub feature enabled unless explicitly reviewed.
