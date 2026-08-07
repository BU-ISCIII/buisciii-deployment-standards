# Application Installation Implementation Checklist

Application:

Repository:

Reviewer and date:

Applicable profiles:

For each item, link to the exact file, command, test result, or tracked issue.

## A. Documentation implemented

- [ ] `README.md` identifies every service and external dependency.
- [ ] `README.md` shows the required repository/directory layout.
- [ ] `README.md` distinguishes local test, production container, and bare-metal
      support.
- [ ] `README.md` lists minimum host, engine, database, DNS, TLS, port, and
      storage requirements.
- [ ] `README.md` includes copyable test install and verification commands.
- [ ] `README.md` includes copyable production install commands.
- [ ] `README.md` inventories every persistent database, volume, and bind mount.
- [ ] `README.md` documents routine status, logs, restart, and shell commands.
- [ ] `README.md` links to the full operator runbook.
- [ ] `LEAME.md` records production preparation in execution order.
- [ ] `LEAME.md` includes pre-install and pre-upgrade backup commands.
- [ ] `LEAME.md` includes first installation and upgrade commands.
- [ ] `LEAME.md` includes permission repair for rootless Podman/SELinux.
- [ ] `LEAME.md` includes smoke tests for local and public endpoints.
- [ ] `LEAME.md` explains application-only rollback versus database restore.
- [ ] `LEAME.md` contains real application recovery and troubleshooting details,
      with all `CHANGE_ME` markers resolved before production approval.

## B. Configuration implemented

- [ ] `conf/docker_test_settings.txt` has safe, disposable local values.
- [ ] `conf/docker_production_settings.txt` is a secret-free production template.
- [ ] `conf/INSTALL_SETTINGS.md` documents every setting, owner, requirement,
      secret classification, scope, default, and build/runtime timing.
- [ ] Production configuration uses a separate ignored file with mode `0600`.
- [ ] `.gitignore` excludes production configuration, generated runtime
      environment, backups, dumps, and synchronization candidates.
- [ ] Installer validation rejects missing production values and `CHANGE_ME`.
- [ ] `DEBUG`, allowed hosts, CSRF, CORS, proxy headers, and email behavior are
      explicitly configured.
- [ ] Shared identity, API, frontend, and proxy URLs have one documented source
      of truth.
- [ ] No committed production or sample secret is accepted in production mode.

## C. `install.sh` implemented

- [ ] Recognizes every canonical `install.sh` option from the installation
      contract; it is not required to recognize container-installer options.
- [ ] `--help` and `--version` make no changes and return success.
- [ ] Unsupported actions fail explicitly before making changes.
- [ ] Validates the selected settings file and required values.
- [ ] Handles `current`, branch, tag, and commit revision semantics as documented.
- [ ] `--stage` installs dependencies and files without database access,
      runtime secrets, migrations, fixtures, or user creation.
- [ ] `--bootstrap` requires a staged tree and runs checks, pre-migration hooks,
      migrations, optional fixtures, post-migration hooks, and static collection
      in that order.
- [ ] Repeatable `--script_before` and `--script_after` hooks have been tested
      during a representative upgrade.
- [ ] `--tables` and `--skip_tables` behave explicitly; production upgrades
      skip fixtures unless requested.
- [ ] Installs dependencies into a predictable virtual environment.
- [ ] Stages only reviewed application files and preserves runtime data.
- [ ] Preserves Django `SECRET_KEY` and other persistent secrets during upgrade.
- [ ] Runs Django checks, migrations, and static collection in reviewed order.
- [ ] Does not create a production default superuser.
- [ ] Does not load test fixtures during production installation or upgrade.
- [ ] Is safe to rerun or clearly documents non-idempotent steps.
- [ ] Passes `bash -n` and ShellCheck, with reviewed suppressions only.

## D. `container_install.sh` implemented

- [ ] Recognizes every canonical `container_install.sh` option from the
      installation contract; it is not required to recognize `install.sh`
      workflow options.
- [ ] Selects test and production Compose files deterministically.
- [ ] Requires explicit production configuration.
- [ ] Supports Docker and rootless Podman, or rejects an unsupported engine.
- [ ] Runs `compose config` before building or starting services.
- [ ] Creates only the exact required host directories.
- [ ] Implements `fix-permissions` without rebuilding, migrating, or deleting.
- [ ] Builds the selected immutable revision and records it.
- [ ] Waits on dependency health rather than a fixed startup sleep.
- [ ] Separates image staging from runtime database/bootstrap work.
- [ ] Builds through `install.sh --stage` and invokes `install.sh --bootstrap`
      only after the container and dependencies start.
- [ ] Passes pre/post migration hooks and fixture choices into bootstrap.
- [ ] Supports a Compose-file override and recognizes service-specific
      configuration mapping for orchestrators.
- [ ] Runs migrations once and stops on failure.
- [ ] Prints container logs when readiness fails.
- [ ] Prints URLs and verification commands on success.
- [ ] Upgrade preserves all volumes and bind-mounted data.
- [ ] Passes `bash -n` and ShellCheck, with reviewed suppressions only.

### Orchestrator-specific checks

- [ ] Descriptor has one `SERVICES` entry per application and selects the
      correct profile independently for each service.
- [ ] At most one service uses build context `.`, and that service's generated
      profile artifacts belong to the current repository.
- [ ] Every service declares its profile, build context, Dockerfile and
      production/test configuration; Django also declares `PROJECT_MODULE`.
- [ ] `REPO_PATH`, `INSTALL_PATH`, host persistence paths, `APP_PORT`, and
      UID/GID exist only in service settings and reach Dockerfile/Compose
      through the generated environment, never duplicate `project.json` keys.
- [ ] `install_services` contains application services in build/bootstrap order.
- [ ] `permission_services` contains applications plus every selected add-on.
- [ ] `configured_services` contains only applications; each add-on reads its
      namespaced section from the selected application's settings file.
- [ ] Multi-app add-ons use `CONFIG_SERVICE` only when the first application
      service does not own their configuration section.
- [ ] Django services receive stage/bootstrap and protected settings rendering;
      React services explicitly skip Django bootstrap.
- [ ] Production Django builds use direct engine build secrets; React builds
      receive only reviewed public `VITE_*` arguments.
- [ ] Each application and add-on has separate host-bind and running-container
      permission specifications, including explicit empty specifications.

## E. Docker image implemented

- [ ] `.dockerignore` excludes operator settings and temporary configuration copies, re-including only safe test settings/templates.
- [ ] Production build passes the single operator configuration with `--secret`; Dockerfile consumes it with `RUN --mount=type=secret`.
- [ ] Production staging disables settings rendering and test staging explicitly enables it.
- [ ] Verified the production settings file is absent from the build context and final image.
- [ ] `Dockerfile` uses an approved and deliberately versioned base image.
- [ ] Required system packages are explicit and caches are cleaned.
- [ ] Application dependencies and code are staged during image build.
- [ ] Runtime does not depend on a mutable source checkout.
- [ ] Container runs as a numeric non-root UID/GID.
- [ ] Entrypoint uses `exec` so signals reach Gunicorn.
- [ ] Entrypoint stops on failed checks or migrations.
- [ ] Health check tests an application endpoint.
- [ ] Build context excludes secrets, dumps, logs, VCS data, and virtualenvs.
- [ ] Image builds for every supported architecture or states its limitation.

## F. Compose implemented

- [ ] Exactly one generated test Compose file and one generated production
      Compose file contain all selected service profiles and add-ons.
- [ ] No operator command requires multiple `-f` Compose overlays.
- [ ] Managed service/add-on blocks have stable `BEGIN/END BU-ISCIII` markers.
- [ ] Apache routes target declared services and its generated configuration is
      mounted read-only with a separate host permission specification.
- [ ] Multi-app Apache uses one `VIRTUAL_HOSTS` entry per DNS name; path-based
      `ROUTES` are used only for applications tested under those URL prefixes.
- [ ] Apache receives forwarded protocol/port and request-size values in its
      container environment, and its proxy timeout matches application needs.
- [ ] Apache mounts each Django static/document source read-only, uses a
      persistent production log bind, and labels every extra mount as required,
      generated multi-app, or optional application policy.
- [ ] Keycloak and `keycloak_db` have health/dependency ordering, protected
      production database/admin settings, a read-only realm import bind and
      persistent `keycloak_db_data` included in backup/restore procedures.
- [ ] Realm import JSON is generated reproducibly and operators understand that
      `--import-realm` does not overwrite an existing realm.
- [ ] Keycloak, Keycloak DB and Apache each retain separate host/running-mount
      permission specifications, including explicit empty specs.

- [ ] Test Compose includes an isolated database with a health check.
- [ ] Test ports bind to loopback unless external access is intentional.
- [ ] Test state survives restart and is removable with an explicit `down -v`.
- [ ] Production Compose uses the documented external database model.
- [ ] Production database ports are not published.
- [ ] Public access is through loopback or the approved reverse proxy.
- [ ] Persistent documents, logs, static files, and other data are all mounted.
- [ ] Rootless Podman/SELinux volume labels have been tested.
- [ ] Service dependencies use health/readiness conditions where supported.
- [ ] Image tags and externally supplied images follow the version policy.
- [ ] `docker compose config` and the supported Podman Compose command succeed.

## G. Backup, restore, rollback, and acceptance tested

- [ ] A clean test installation passes from a fresh database volume.
- [ ] A production-like installation passes with an external database.
- [ ] Restart and container recreation preserve required data.
- [ ] Upgrade from the currently supported release preserves data.
- [ ] Database and filesystem backups have been created and inspected.
- [ ] A backup has been restored into a clean recovery target.
- [ ] Application-only rollback has been tested where schema-compatible.
- [ ] Database-plus-files rollback has been tested where required.
- [ ] Smoke test checks health, migrations, a real read, authentication when
      applicable, and an application-specific workflow.
- [ ] Public HTTPS, proxy headers, static files, email, and scheduled jobs have
      been verified where applicable.
- [ ] Installation, upgrade, restore, and rollback evidence is retained.

## Findings and intentional exceptions

| Requirement | Status | Evidence or corrective action | Owner | Review date |
|---|---|---|---|---|
| | | | | |
