# Deployment workflow

This guide is the practical path from a generated, configuration-ready repository to a verified test or production deployment. It assumes the application has already been scaffolded; use [Creating a project](creating-a-project.md) for initial generation.

## 1. Synchronize with the deployment standard

Deployment starts with a synchronization gate. Select and record the approved commit or version of `buisciii-deployment-standards`, check the application against that exact revision, and continue only when every reported item is `current`.

From the selected standards checkout, run:

```bash
python3 /path/to/buisciii-deployment-standards/scripts/scaffold.py \
  check /path/to/application
```

If the check reports any other status, stop the deployment. Follow the [Scaffold workflow](scaffold-workflow.md) to synchronize the application, resolve managed or contract drift, run the check again, review the result, and commit the synchronized files and `.bu-isciii-deployment/state.json`. Then return to this workflow.

A successful check proves synchronization with the selected standards revision. It does not prove that infrastructure, configuration, or the running application is ready.

## 2. Before you start

Confirm that the host meets the [infrastructure requirements](../standards/infrastructure-requirements.md). For a new development host, follow [Requesting a virtual machine](requesting-a-virtual-machine.md). Before a production deployment, complete [Preparing production infrastructure](preparing-production-infrastructure.md).

Have these ready:

- a clean, reviewed application revision;
- Docker or Podman with Compose support;
- access to the host, image sources, and secret/configuration stores;
- the generated `container_install.sh`, Compose files, settings templates, and `scripts/smoke_test.sh`;
- persistence and backup plans for stateful services; see [Backups and restore](backups-and-restore.md);
- application-specific acceptance checks and a deployment owner.

Both Docker and Podman are supported. Choose the engine installed and approved on the host; do not assume Docker is rootless.

## 3. Confirm the synchronized scaffold

The synchronization check above is the required scaffold validation. Confirm its successful output identifies no synchronization issues before continuing.

If generated shell scripts were changed locally, perform the syntax checks used by the test suite:

```bash
bash -n container_install.sh
bash -n scripts/smoke_test.sh
```

Review the [application profiles](../profiles/README.md) and [addons](../addons/README.md) selected by the descriptor.

## 4. Prepare configuration

Start with test. Complete its generated settings, including ports, credentials, service URLs, and application values. Follow [Configuration](configuration.md) and [Docker Compose](docker-compose.md).

For production:

1. Copy each production settings template to a protected operational location, normally under `deployment/settings/`.
2. Replace every required placeholder, especially `CHANGE_ME`.
3. Restrict access to secrets and production settings.
4. Use `--install_conf` for the first application service, or repeat `--install_conf_map component,path` for explicit per-component mappings.

The installer rejects an active production configuration containing `CHANGE_ME`. Do not commit production secrets or place them in generated templates.

Use the [container installer reference](../reference/scripts/container-install.md) for authoritative mappings and CLI details. Follow [Container install customization](container-install-customization.md) for deliberate extensions.

## 5. Validate deployment configuration

Configuration validation is a required gate in every install. The generated installer performs it automatically after rendering the selected settings and validating the final Compose model, but before building any image or recreating any service.

The check cross-validates the generated environment, Compose services, application profiles, and rendered Apache routes. Depending on the selected components, it detects unresolved production placeholders, unknown internal hosts, incorrect upstream ports, invalid loopback proxy targets, database-service mismatches, Django host mismatches, and inconsistent Keycloak or canonical URLs.

Production findings fail the installation. Test findings are reported as warnings where the implementation permits test-only shortcuts. Review warnings rather than treating them as successful acceptance. The checker does not prove that external DNS, databases, identity providers, email, or other remote services are reachable.

When the installer reports `Deployment configuration check failed`, correct the selected settings or component mapping and rerun the same install command. See [Configuration](configuration.md) for the validation boundaries and the [shared container library](../../lib/container/README.md#deployment-configuration-check) for exact rules.

## 6. Deploy to test

Use the engine available on the test host:

```bash
bash container_install.sh \
  --test \
  --action install \
  --engine docker
```

For Podman, replace `docker` with `podman`.

Install validates configuration and Compose input, prepares host paths and permissions, builds images, recreates services, waits for profile readiness, runs profile bootstrap, optionally loads profile-owned test/demo data, and runs the generated smoke test. Test/demo data is not loaded implicitly in production.

## 7. Review test

Do not promote solely because containers are running. Confirm:

- expected application and add-on services are present;
- the installer and smoke test pass;
- each application responds at `/health/`;
- application checks such as login, a representative read/write flow, and integrations pass;
- logs have no unresolved startup, migration, or permission errors;
- persistent data survives service recreation where required;
- mounted paths are writable by the intended container users;
- only intended test/demo data was loaded.

Fix failures and repeat until shared smoke checks and application acceptance checks pass.

## 8. Prepare production

| Area | Test | Production |
| --- | --- | --- |
| Configuration | Test settings | Protected, completed production settings |
| Revision | Development revision may be acceptable | Reviewed tag or immutable commit |
| Data | Profile-owned test/demo data may be enabled | No implicit test/demo data |
| Persistence | May be disposable | Retention, ownership, and backup confirmed |
| Acceptance | Smoke and application checks | Smoke, application, and operational checks |

Before the production window:

1. Choose the reviewed tag or commit and ensure the build context contains that source.
2. Verify production mappings and remove placeholders.
3. Confirm volumes, ownership, capacity, and backup/restore arrangements.
4. Review [Upgrades and rollback](upgrades-and-rollback.md).
5. Confirm monitoring, routing, certificates, acceptance checks, and the rollback decision owner.

The `--git_revision` value is passed into the profile build/install flow and recorded by profiles that support it. It does not replace verifying the source/build context.

## 9. Deploy to production

For example:

```bash
bash container_install.sh \
  --action install \
  --engine podman \
  --git_revision v1.2.3 \
  --install_conf_map example-app,deployment/settings/example-app_production_settings.txt
```

Replace the revision, engine, component, and path. Repeat `--install_conf_map` for every component needing an explicit mapping. With one application service, `--install_conf path` is the shorter equivalent for that first service. Do not add `--test` in production.

## 10. Readiness and bootstrap

The generated lifecycle is:

1. Validate configuration and Compose input.
2. Build images and recreate services.
3. Wait for each profile readiness file.
4. Run profile bootstrap callbacks.
5. Load optional profile-owned data.
6. Run the shared smoke test.

A readiness file means bootstrap may begin; it is not final acceptance.

Bootstrap is profile-specific. Django validates database access and runtime configuration, runs deployment checks, verifies and applies migrations, optionally creates configured first tables, runs hooks, collects static files, and verifies migrations. Generated Next.js and React/Vite profiles currently have no runtime bootstrap. Consult the [profile documentation](../profiles/README.md) instead of assuming every profile performs database work.

## 11. Smoke test and acceptance

The generated `scripts/smoke_test.sh` selects Docker or Podman, validates resolved Compose configuration, runs generated profile checks, and checks each application at `http://127.0.0.1:<port>/health/`.

A passing shared smoke test is necessary, not sufficient. Also run release-specific functional and production operational checks. See the [smoke test reference](../reference/scripts/smoke-test.md).

## 12. After deployment

Record the environment, date, operator, revision, image identifiers, configuration mappings (without secret values), bootstrap outcome, service status, smoke and acceptance results, backup verification, and rollback point.

Verify public routing and certificates, monitoring and alerts, persistence, scheduled jobs, and downstream integrations. Put application-specific details in generated `LEAME.md` or the operational release record instead of duplicating shared standards here.

## Failure paths

### Configuration or Compose validation fails

Correct settings or Compose input and rerun. This occurs before build and service recreation, although host paths and initial permissions may already have been prepared.

### Readiness times out

Inspect service status and logs with the selected engine's Compose command. Fix startup, dependency, configuration, or permission errors, then rerun. A running container alone is not ready.

### Bootstrap fails

Read the profile bootstrap output. Resolve migration, database, hook, static-file, or application validation errors. Before rerunning, determine whether bootstrap made a partial state change.

### Smoke or acceptance fails

Keep the release unapproved. Inspect service logs and the failing path. Fix and redeploy, or use the reviewed [rollback procedure](upgrades-and-rollback.md).

### Mounted-file permissions are wrong

Use the installer action instead of ad hoc recursive changes:

```bash
bash container_install.sh \
  --action fix-permissions \
  --engine docker
```

Use `podman` when appropriate and supply the same configuration mappings required by that environment. This prepares host and running-container mount permissions, then exits without builds, bootstrap, data loading, or smoke tests. See [container installer reference](../reference/scripts/container-install.md).
