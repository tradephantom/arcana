# ARCANA Paper Package

This folder contains the venue-neutral LaTeX source generated from the reviewed
public manuscript.

Source authority and claim boundary are declared in `SOURCE.json`. The builder
fails if the reviewed Markdown hash changes, if the generated LaTeX differs
from the checked-in artifact, or if private/internal claim tokens enter the
paper.

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
