# ARCANA Public Release Policy

> Status: local-first release policy v0.1
> Scope: this local public repository

This repository is the local public-track ARCANA workspace.

The internal ARCANA research workspace is separate. This repository should contain only files intended for public review or publication.

## Remote Policy

Do not create or push a remote repository until:

- `make check` passes locally;
- all files are listed in `PUBLIC_MANIFEST.md`;
- public schemas use public IDs;
- examples and fixtures are synthetic or public-source safe;
- no private enterprise, customer, or lab details are present;
- no paid GitHub feature is needed for the current milestone.

Initial remote publication should use:

- no GitHub Actions by default;
- no Git LFS;
- no Packages;
- no Codespaces;
- no larger hosted runners.

CI can be added later only after local checks are stable and billing controls are explicitly reviewed.

## Local-First Development Rule

All implementation and audit work starts locally.

The remote public repository is a publication channel, not the development authority.

## Required Local Gate

Run:

```sh
make check
```

before every commit and before any remote push.
