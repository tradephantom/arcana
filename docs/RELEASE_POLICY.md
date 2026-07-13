# ARCANA Public Release Policy

> Status: local-first release policy v0.1
> Scope: this local public repository

This repository is the local public-track ARCANA workspace.

The internal ARCANA research workspace is separate. This repository should contain only files intended for public review or publication.

## Remote Policy

Do not create or update a public remote repository until:

- `make check` passes locally;
- `make test` passes locally;
- `make demo` passes locally;
- all files are listed in `PUBLIC_MANIFEST.md`;
- `LICENSE.md` contains the final license profile;
- `SECURITY.md` names GitHub Private Vulnerability Reporting;
- public schemas use public IDs;
- examples and fixtures are synthetic or public-source safe;
- no private enterprise, customer, or lab details are present;
- no paid GitHub feature is needed for the current milestone.

The initial remote publication used no hosted CI. GitHub Actions is now
approved only under this controlled public-CI profile:

- the sole workflow is `.github/workflows/ci.yml`;
- only standard Ubuntu GitHub-hosted runners are allowed;
- workflow permissions are read-only and no repository secrets are used;
- external Actions are limited to approved GitHub-owned Actions pinned to full
  commit SHAs;
- no workflow artifact or cache storage is persisted;
- no Git LFS;
- no Packages;
- no Codespaces;
- no GitHub Pages;
- no larger hosted runners.

The CI and billing review was completed on 2026-07-13. Standard hosted runners
for this public repository are accepted; paid/larger runners and paid storage
remain prohibited without a new explicit review.

## Local-First Development Rule

All implementation and audit work starts locally.

The remote public repository is a publication channel, not the development authority.

## Required Local Gate

Optional local environment setup:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run:

```sh
make check
make test
make demo
```

before every commit and before any remote push.

GitHub CI is an independent reproduction surface, not a replacement for this
local gate and not evidence of production readiness, peer review, or A2/A3
calibration.
