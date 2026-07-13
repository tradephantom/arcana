# ARCANA Public Release Notes v0.1.1

> Release class: open research/reference archival update
> Release date: 2026-07-13
> Paper DOI: 10.5281/zenodo.21333463
> Claim boundary: research/reference only; no production authority

## Scope

Release `v0.1.1` completes the publication metadata and archival package for
the ARCANA v1.0 preprint. It does not change ARCANA's admission semantics,
calibration evidence class, or production authority.

## Publication Additions

- identifies Julio Elizondo Rodriguez, TradePhantom LLC, as author;
- restores the canonical expansion, Autonomy Risk Calculus for Agentic Network
  Assurance, as the paper title and project identity;
- binds the preprint to DOI `10.5281/zenodo.21333463`;
- adds formal primary references and the public relationship to AXCP without
  making AXCP a dependency;
- adds `CITATION.cff` with a preferred citation for the preprint;
- adds a machine-readable paper publication contract;
- records the paper license as `CC-BY-4.0` while preserving `Apache-2.0` for
  code, tests, tools, schemas, examples, and build files;
- preserves deterministic replay of the immutable `v0.1.0` release.

## Evidence Boundary

The DOI provides a persistent scholarly identifier and publication timestamp.
It does not constitute external peer review, empirical deployment validation,
production enforcement approval, or proof of absolute safety.

## Local Verification

```sh
make check
make test
make demo
make bench
make paper-check
make paper
```

The distributed PDF, source archive, benchmark report, and checksum manifest
must be tied to the exact `v0.1.1` release commit.
