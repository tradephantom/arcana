# ARCANA Public Manifest

> Status: public staging manifest v0.1
> Scope: files intended to seed a future public ARCANA repository

Only files listed here are part of this public release candidate tree.

## Included Files

| Path | Status | Notes |
| --- | --- | --- |
| `README.md` | public-staging | Public release workspace instructions. |
| `PUBLIC_MANIFEST.md` | public-staging | Manifest of public release candidates. |
| `.gitignore` | public-staging | Local development exclusions. |
| `Makefile` | public-staging | Local check entrypoint. |
| `docs/README.md` | public-staging | Public documentation index. |
| `docs/ARCANA_PRD_v0.2_Public.md` | public-safe draft | Public PRD draft; review required before remote publication. |
| `docs/ARCANA_Roadmap_v0.1_Public.md` | public-safe draft | Public roadmap draft; review required before remote publication. |
| `docs/RELEASE_POLICY.md` | public-staging | Local-first release and remote policy. |
| `tools/audit_public.py` | public-staging | Public release-boundary audit script. |

## Release Checklist

- [ ] All public files are listed in this manifest.
- [ ] No file contains local filesystem paths.
- [ ] No file contains private implementation details.
- [ ] No file contains private lab or customer operational details.
- [ ] No file uses private or adapter-specific reason codes as the public default.
- [ ] No file claims absolute safety, risk elimination, or production certification from demo calibration.
- [ ] Schema IDs, if present, use public namespaces.
- [ ] Examples and fixtures, if present, are synthetic or public-source safe.
