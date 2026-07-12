# ARCANA Public Remote Preflight v0.1

> Status: public remote preflight checklist v0.1
> Scope: checklist for creating, pushing, and validating the public GitHub remote
> Remote status: public remote is live and validated
> License decision: final public license profile is defined in `LICENSE.md`
> Security decision: GitHub Private Vulnerability Reporting is enabled for the public remote

This checklist controls when the local public-track repository can be published to a public GitHub remote and how follow-up public updates are validated.

The remote repository is a publication channel. It is not the development authority.

## 1. Hard Rule

Do not create or push a public remote unless every item in this document passes.

The source for publication is this public-track repository only. Do not publish the parent research workspace or any workspace that contains private operational material.

## 2. Required Local State

Before remote creation:

- `git status --short` is clean;
- `git remote -v` is empty or points only to an explicitly approved public remote;
- `make check` passes;
- `make test` passes;
- `make demo` passes;
- `make bench` passes;
- `python -m compileall -q src` passes;
- `git diff --check` passes;
- all public files are listed in `PUBLIC_MANIFEST.md`;
- `LICENSE.md` contains the final license profile;
- `SECURITY.md` names GitHub Private Vulnerability Reporting;
- `docs/LIMITATIONS_v0.1.md` is present;
- `docs/ARCANA_Whitepaper_v0.2_Draft.md` remains marked as a review draft.

## 3. Boundary Checks

The public tree must contain no:

- local filesystem paths;
- private implementation details;
- customer identifiers;
- private telemetry;
- private policy profiles;
- non-public calibration profiles;
- private evidence payloads;
- private deployment URLs;
- private adapter reason codes;
- production certificate claim from A0 output;
- claim that ARCANA proves safety or eliminates risk.

Synthetic examples must stay synthetic and visibly labeled.

## 4. GitHub Cost Controls

Initial remote publication must use:

- no GitHub Actions by default;
- no Git LFS;
- no GitHub Packages;
- no Codespaces;
- no GitHub Pages;
- no larger hosted runners;
- no paid GitHub feature unless explicitly reviewed.

Local checks remain the authority until billing and CI controls are reviewed.

## 5. Remote Creation Sequence

When publication is approved:

1. Create an empty public GitHub repository.
2. Do not add a generated README, license, or gitignore in GitHub.
3. Keep GitHub Actions disabled or unused.
4. Add the remote locally only after the repository is empty and reviewed.
5. Push the local `main` branch.
6. Enable GitHub Private Vulnerability Reporting.
7. Confirm `SECURITY.md` appears on the default branch.
8. Confirm no paid features were enabled.
9. Clone the public remote into a separate temporary directory.
10. Run `make check`, `make test`, `make demo`, and `make bench` from the fresh clone.

Do not announce or link the public remote until steps 6 through 10 pass.

## 6. Post-Push Validation

After the first push:

- verify `PUBLIC_MANIFEST.md` matches the remote tree;
- verify license rendering in GitHub matches the intended profile;
- verify `SECURITY.md` is visible;
- verify GitHub Private Vulnerability Reporting is enabled;
- verify no workflow files are present unless explicitly approved;
- verify no large files or binary artifacts were introduced;
- verify examples remain synthetic;
- verify the manuscript status matches the current review decision and does not imply production approval.

## 7. Stop Conditions

Stop before push or announcement if:

- public audit fails;
- schema validation fails;
- tests fail;
- demo fails;
- benchmark fails;
- worktree is dirty;
- manifest has unlisted files;
- final license profile is changed without review;
- GitHub Private Vulnerability Reporting cannot be enabled;
- a paid feature is required;
- any private or sensitive material is discovered.

If a stop condition occurs, fix locally and rerun all gates before continuing.

## 8. Rollback Guidance

If a private or sensitive artifact reaches the remote:

1. stop public promotion immediately;
2. disable public announcement paths;
3. preserve local evidence for review;
4. remove or restrict the remote according to maintainer policy;
5. rotate any affected credentials if applicable;
6. add a regression test or audit rule before retrying.

Do not treat deletion alone as sufficient when sensitive material may have been cloned.

## 9. Current Publication Status

As of 2026-07-05:

- final license profile is decided;
- security channel is decided;
- public remote is live at `https://github.com/tradephantom/arcana`;
- GitHub Private Vulnerability Reporting is enabled;
- GitHub Actions is disabled;
- GitHub Pages is absent;
- fresh-clone validation passed with `make check`, `make test`, `make demo`, and `make bench`;
- public production claims are not authorized;
- final whitepaper or paper publication is not yet authorized.

The next publication action is maintainer-approved public-safe messaging or a
separate final whitepaper/paper publication decision.
