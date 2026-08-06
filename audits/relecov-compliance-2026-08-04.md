# RELECOV installation contract audit

Date: 2026-08-04

Repositories:

- `relecov-platform`: integrated RELECOV Platform orchestrator
- `relecov-iskylims`: standalone iSkyLIMS component

This is a source and configuration audit. Compose models and shell syntax were
validated, but a clean installation, upgrade, backup restore, and rollback were
not executed because no RELECOV test containers were running during the audit.

## Executive result

Both repositories contain mature installation code and unusually complete
operational documentation. They establish most of the behavior captured by the
contract, especially stage/bootstrap separation, rootless Podman handling,
pre/post migration hooks, persistence, backups, and rollback.

They do not yet fully meet the contract. The main gaps are the canonical CLI,
side-effect-free help/version handling, automated smoke-test execution evidence,
application health checks in Compose, and a complete per-setting configuration
reference.

| Area | RELECOV Platform | iSkyLIMS | Finding |
|---|---|---|---|
| Infrastructure and topology documentation | Meets | Partial | Platform includes an integrated topology; iSkyLIMS documents standalone layout but could add a diagram |
| Test installation | Meets | Meets | Both have test Compose and documented commands |
| Production installation | Meets | Meets | Both have production Compose, external DB configuration, and Podman guidance |
| Stage/bootstrap separation | Meets | Meets | Implemented in both `install.sh` files and used by image/container workflows |
| Pre/post migration hooks | Meets | Meets | Repeatable hooks implemented and forwarded by container installers |
| Upgrade documentation | Meets | Meets | Both document container and bare-metal upgrades |
| Persistence and permissions | Meets | Meets | Host paths, named volumes, UID/GID, and repair behavior documented |
| Backup and rollback | Meets | Meets | Commands and decision guidance exist; restore-test evidence remains required |
| Canonical installer CLI | Mostly meets | Mostly meets | Both script families established the canonical interfaces; help/version behavior and explicit unsupported-option handling still need correction |
| Help/version safety | Does not meet | Does not meet | `install.sh --help` exits through Git cleanup and emitted fatal Git errors when invoked outside the repository directory |
| Configuration reference | Partial | Partial | Templates are commented, but neither repository has a complete `conf/INSTALL_SETTINGS.md` matrix |
| Compose application health checks | Partial | Partial | Database test services have health checks; application, iSkyLIMS, Nextstrain, and production proxy services lack consistent Compose health checks |
| Automated smoke test | Implemented, runtime pending | Implemented, runtime pending | Scripts were added in this audit and passed static validation; a running-stack exercise is still required |
| Restore exercise | Unverified | Unverified | Documentation exists, but evidence of restoration into a clean target was not available |

## Contract findings

### P0 — validate before production adoption

1. Run both new smoke tests against clean test installations using Docker and
   the production engine (normally rootless Podman).
2. Execute an upgrade from the oldest supported release using representative
   `--script_before` and `--script_after` hooks.
3. Restore database and persistent files into a clean recovery target and retain
   evidence.

These are validation gaps rather than known code defects, but the contract does
not consider the procedures complete without execution evidence.

### P1 — installer interface and behavior

1. Make `install.sh --help` and `--version` return success without installing traps,
   changing Git state, or requiring the caller to be in the repository.
2. Ensure every `install.sh` exposes the same `install.sh` options and every
   `container_install.sh` exposes the same container-installer options; the two
   script types do not need to share one combined interface.
3. Correct the Platform container installer description, which currently says
   it installs iSkyLIMS even though it owns the integrated RELECOV stack.
4. Explicitly recognize non-applicable options within each script family's
   interface and fail before making
   changes.

### P1 — health and acceptance

1. Add health endpoints that do not require authentication and report at least
   application and database readiness.
2. Add Compose health checks for application services and production proxies.
3. Decide whether Nextstrain readiness is only HTTP availability or also
   requires an expected dataset.
4. Extend smoke tests with an authenticated business operation where stable
   non-production credentials can be provisioned safely.
5. Add Samba read/write validation to iSkyLIMS test acceptance; container
   running state alone is insufficient.

### P2 — configuration and documentation

1. Create `conf/INSTALL_SETTINGS.md` in both repositories with requirement,
   secret classification, build/runtime timing, and network scope for every
   setting.
2. Add an explicit supported-capabilities table to both READMEs.
3. Record external ownership of TLS, SMTP, database backups, monitoring, and
   secrets.
4. Add a concise standalone topology diagram to iSkyLIMS.
5. Document image-version policy. Several external images are floating or not
   digest-pinned.

## Smoke tests added

### Integrated Platform smoke test

`relecov-platform/scripts/smoke_test.sh` checks:

- Compose rendering;
- running state for Platform, iSkyLIMS, Nextstrain, and the applicable database
  or Apache service;
- Django system checks in both applications;
- unapplied migrations in both applications;
- direct test HTTP endpoints for Platform, schema, iSkyLIMS, Swagger, and
  Nextstrain;
- production Apache routing using three configurable Host headers.

### Standalone iSkyLIMS smoke test

`relecov-iskylims/scripts/smoke_test.sh` checks:

- Compose rendering;
- application plus test database/Samba or production Apache running state;
- Django system checks and unapplied migrations;
- application root and Swagger through the selected URL/Host header.

Both scripts support Docker, Podman, Compose overrides, environment-file
selection, HTTP overrides, and a diagnostic `--skip_http` mode.

## Synchronization safety exercise

The scaffold was initialized against full temporary copies of both repositories.
No existing source file changed:

- Platform: 11 existing files were preserved and received
  `.bu-isciii-update` candidates.
- iSkyLIMS: 12 existing files were preserved and received
  `.bu-isciii-update` candidates.
- New files such as the settings reference and generic smoke test were added
  only to the temporary copies.

The conflict strategy therefore protects the working installation. Directly
enrolling the real repositories now would, however, create many candidate files
that are generic and less capable than the existing RELECOV implementation.

Recommended adoption:

1. Keep the real repositories uninitialized while this audit is resolved.
2. Treat the existing RELECOV files as the functional source for improving the
   central scaffold.
3. Reconcile one managed file at a time, beginning with smoke tests and settings
   documentation.
4. Initialize scaffold state only after each current application file is
   intentionally accepted as equivalent to or more capable than its template.
5. On every later sync, review `.bu-isciii-update` candidates and run syntax,
   Compose, test-install, upgrade, and smoke validation before merging.

## Commands required to complete runtime validation

From `relecov-platform`:

```bash
bash container_install.sh --test --engine docker --git_revision current
bash scripts/smoke_test.sh --test --engine docker
```

From `relecov-iskylims` for its standalone stack:

```bash
bash container_install.sh --test --engine docker --git_revision current
bash scripts/smoke_test.sh --test --engine docker
```

Production-like Podman validation must use non-production databases and host
paths prepared specifically for acceptance testing.
