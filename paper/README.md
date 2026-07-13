# ARCANA Paper Package

This folder contains the venue-neutral LaTeX source generated from the reviewed
public manuscript.

Source authority and claim boundary are declared in `SOURCE.json`. Author,
archive, DOI, license, and citation identity are declared in
`PUBLICATION.json`. The builder fails if either bound source hash changes, if
publication identity diverges across the manuscript, metadata, or title style,
if the generated LaTeX differs from the checked-in artifact, or if
private/internal claim tokens enter the paper.

`reviewed_public_commit` and `reviewed_public_tree` identify the technical
claim-review baseline. Subsequent attribution, bibliography, archive, and DOI
metadata are separately hash-bound by `SOURCE.json` and become immutable at the
release commit.

Required local tools:

```text
Python 3.11 or newer
Pandoc 3.10
Tectonic 0.16.9
```

The exact document-tool versions are pinned in `SOURCE.json`. A version
mismatch fails with a specific build reason instead of producing an artifact
whose byte-level reproducibility has not been established.

Generate and compile:

```sh
make paper
```

Verify that the checked-in LaTeX is reproducible without writing it:

```sh
make paper-check
```

Generated PDF and TeX auxiliary files are written under `build/paper/` and are
not public repository source artifacts. Any distributed PDF must carry an
external checksum and release record tied to the exact source commit.

The v1.0 preprint DOI is `10.5281/zenodo.21333463`. The DOI identifies the
archival preprint; it does not imply external peer review, empirical deployment
validation, or production authority.
