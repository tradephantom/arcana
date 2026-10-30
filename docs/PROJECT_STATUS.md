# ARCANA Project Status

As of: 2026-10-30. Scope: public research/reference only.

This is the current navigation index. Dated release notes and paper artifacts
describe their own revisions, not later code. PRD v0.2 remains the public scope
contract; the public roadmap carries the corrective sequence.

| Surface | State |
| --- | --- |
| Archived software | v0.1.1 at `ca14464a19a9dfaedbb8b3c76bd0d030df6f13b5`, unchanged; superseded by v0.1.2 because it can under-report extreme spectral radii |
| Archived preprint | Paper v1.0, DOI `10.5281/zenodo.21333463`, unchanged |
| R1 | Numerical/input correction merged by PR #3 at `aaed2db55d889b43714135bfb9774e7ae46f4e9b`; post-merge checks passed |
| R2 | Packaging/provenance correction merged by PR #4 at `be4383c` |
| Corrective release | v0.1.2 ships R1 and R2; see [Release Notes v0.1.2](PUBLIC_RELEASE_NOTES_v0.1.2.md) |
| Next gate | Exact-revision independent review and a separately approved manuscript update |
| Empirical authority | Synthetic benchmark only; no new empirical A2/A3 evidence |
| Production authority | Not provided by this repository or by a green test run |

## Current Contracts

1. [Public PRD](ARCANA_PRD_v0.2_Public.md)
2. [Public Roadmap](ARCANA_Roadmap_v0.1_Public.md)
3. [Numerical Contract v1](NUMERICAL_CONTRACT_v1.md)
4. [Installed Package Contract](PACKAGE_PORTABILITY.md)
5. [Corrective Review Packet](CORRECTIVE_REVIEW_PACKET.md)
6. [Limitations](LIMITATIONS_v0.1.md)

The numerical contract supersedes unchecked spectral-estimate interpretations
for corrected source. It bounds the represented matrix, not calibration truth
or real-world safety. Old benchmark report hashes cannot identify the corrected
evaluator; corrected reports bind its numerical and resource modules as well.

## Identity Discipline

Package metadata and the runtime version identify `0.1.2`, the corrective
release of the R1 and R2 source, not the archived v0.1.1 distribution. Always
bind the exact release commit and wheel hash; the version string alone is not a
source identity. The release tag, package upload and any archive submission
remain separate maintainer decisions.

The v1.0 manuscript, `paper/PUBLICATION.json`, `paper/SOURCE.json` and LaTeX
inputs preserve published attribution and archive provenance. Their
historical metadata must not be silently rewritten to describe R1/R2.
`CITATION.cff` describes the latest software release (v0.1.2, Zenodo DOI
`10.5281/zenodo.23804154`) and keeps the v1.0 preprint as preferred citation.
ARCANA has no dedicated website. The repository is its canonical project URL;
`https://getaxcp.com` identifies the related AXCP project, not an ARCANA site.

Preprint deposit and author metadata are complete for v1.0. Independent peer
review, venue acceptance, review of the corrective revision, and a new-version
submission decision remain separate. No production integration is distributed
here; AXCP Core remains independently usable and external integration optional.
