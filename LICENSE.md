# ARCANA License Notice

> Status: license notice draft
> Scope: local public release candidate
> Publication status: not a final public license grant

ARCANA is intended to be released as open research/reference material, but this local release candidate is not a public distribution until the maintainer approves the final license terms.

## 1. Current License Status

This file records the intended license structure for review. It does not by itself authorize remote publication or public reuse before final maintainer approval.

Until a final license file is approved and committed:

- do not publish this repository as a public remote;
- do not treat this release candidate as a public grant of rights;
- do not accept external contributions;
- do not reuse private, customer, or non-public material in ARCANA public files.

## 2. Intended Release Profile

The intended public release profile is:

| Material | Intended license | Rationale |
| --- | --- | --- |
| Source code under `src/`, `tests/`, and `tools/` | Apache-2.0 | Permissive reference implementation license with patent terms. |
| Public documentation under `docs/` | CC-BY-4.0 | Attribution-friendly research and documentation reuse. |
| Public schemas under `schemas/` | CC0-1.0 or Apache-2.0 | Machine-readable contracts should be easy to implement. |
| Synthetic examples under `examples/` | CC0-1.0 or Apache-2.0 | Synthetic fixtures should be reusable for validation. |

Final license text must be added before remote publication. If the final license split differs from this table, `README.md`, `PUBLIC_MANIFEST.md`, and contribution policy must be updated in the same change.

## 3. No Private Material Grant

No license notice in this public release candidate applies to:

- private operational implementations;
- customer data;
- private telemetry;
- private policy profiles;
- non-public calibration profiles;
- private evidence payloads;
- private lab or enterprise integration material;
- trademarks, names, or branding not explicitly included in the public release.

## 4. Contributor Boundary

External contribution intake must not begin until:

- final license terms are approved;
- `CONTRIBUTING.md` is reviewed;
- `SECURITY.md` is reviewed;
- `docs/LIMITATIONS_v0.1.md` is reviewed;
- public-boundary audit passes;
- every public file is listed in `PUBLIC_MANIFEST.md`.

Contributions must be compatible with the final license terms and must not include private or restricted material.

## 5. Release Gate

Before this repository is published remotely, the maintainer must choose one of these outcomes:

1. replace this notice with final license text;
2. keep this notice and explicitly mark the remote as source-available review material with no public reuse grant;
3. delay remote publication.

Outcome 1 is the preferred path for an open public ARCANA repository.
