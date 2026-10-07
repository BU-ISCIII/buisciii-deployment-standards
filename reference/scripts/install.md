# install.sh reference

## Purpose

container_install.sh orchestrates deployment from the host. install.sh performs profile/application work during an image build or inside a running container.

Only Django currently generates install.sh. Next.js and React/Vite use their Dockerfiles and profile callbacks instead.

For Django, stage and bootstrap are separate:

    Dockerfile build -> install.sh --stage -> staged application image
    running container -> container_install.sh -> install.sh --bootstrap

Stage installs dependencies and constructs the application tree without database access. Bootstrap runs after the outer installer starts the container, waits for readiness, and repairs mounts.

## Interface

    bash install.sh [options]

With no options, the legacy/direct standard workflow runs install/full at revision current with ./install_settings.txt.

| Option | Phase | Purpose |
|---|---|---|
| --stage install\|upgrade | stage | Stage dependencies and application; never touch the DB. |
| --bootstrap install\|upgrade | bootstrap | Run deployment-time Django operations on a staged tree. |
| --install full\|dep\|app | standard | Direct install of dependencies, application, or both. |
| --upgrade full\|dep\|app | standard | Direct upgrade of dependencies, application, or both. |
| --git_revision VALUE | stage/standard | Select local branch, tag, commit, or current. |
| --conf PATH | all | Select normalized installation settings. |
| --render-settings | stage/standard | Render Django settings during staging. |
| --settings-output PATH | stage/standard | Override rendered settings destination. |
| --tables | bootstrap/standard | Load conf/first_install_tables.json. |
| --skip_tables | bootstrap/standard | Disable initial-fixture loading. |
| --script_before SPEC | bootstrap/standard | Repeatable pre-migration runscript. |
| --script_after SPEC | bootstrap/standard | Repeatable post-migration runscript. |
| --script SPEC | bootstrap/standard | Alias for --script_after. |
| --skip_apache_restart | standard | Skip the server-restart hook. |
| --docker | standard | Deprecated alias for --skip_apache_restart. |
| --help, --version | immediate | Print information and exit successfully. |

Generated container deployments use --stage during image construction and --bootstrap after startup. The standard workflow combines them for direct installations.

## Stage

--stage install and --stage upgrade perform the same sequence; the action is available to hooks.

1. Require and source configuration.
2. Record the current Git ref. For a non-current revision, require a clean checkout, verify the commit exists locally, and check it out.
3. Require Python 3.10+, conf/urls.py, the deployment_health.urls include, and configured required modules.
4. Run install_application_system_packages.
5. Create INSTALL_PATH and its virtual environment when absent.
6. Upgrade pip/wheel and install conf/requirements.txt.
7. Require the virtualenv, remove the old generated Django wrapper, and rsync source into INSTALL_PATH while excluding Git, generated, and runtime paths.
8. Create standard runtime directories and call prepare_application_directories.
9. Run django startproject in the clean staged tree.
10. Install generated urls.py, optional routing.py, and custom application files.
11. Write .deployed_revision.
12. Render settings only when enabled, then run runtime-env and permission hooks.
13. Restore the original Git ref on exit when one was recorded.

Stage never checks the database, migrates, loads fixtures, or collects static files.

### Build configuration boundary

The Django Dockerfile calls install.sh --stage install. Test builds use the committed test settings and RENDER_DJANGO_SETTINGS=true, which adds --render-settings.

Production builds mount protected configuration as the build secret install_conf, pass /run/secrets/install_conf to --conf, and set RENDER_DJANGO_SETTINGS=false. Production Django settings are not rendered into the image, and the secret is not copied into an image layer.

## Bootstrap

--bootstrap install or upgrade runs:

1. Require INSTALL_PATH/manage.py and executable INSTALL_PATH/virtualenv/bin/python as proof of staging.
2. Enter INSTALL_PATH and activate the virtualenv.
3. Wait up to 60 seconds for the database, polling every 2 seconds.
4. Call validate_application_runtime.
5. Run manage.py check --deploy.
6. Run each --script_before hook.
7. Run makemigrations --check --dry-run --noinput.
8. Call before_django_migrate with action and MIGRATION_MODULES.
9. Run migrate --noinput.
10. Load the initial fixture when enabled.
11. Run each --script_after hook.
12. Call after_django_migrate with the action.
13. Run collectstatic --noinput.
14. Run showmigrations --plan and fail if it fails or reports an unapplied
    migration.

collectstatic runs for both install and upgrade. Any failure aborts bootstrap.

## Install versus upgrade

Both actions migrate, execute supplied hooks, collect static files, and verify migrations. Install does not assert that the database is empty.

When conf/first_install_tables.json exists, install loads it by default unless --skip_tables is present. Upgrade loads it only with --tables. If both table flags are supplied, the retained skip flag prevents loading; do not combine them.

The default after_django_migrate hook may create the initial superuser only for --bootstrap install and only when explicitly enabled. Other hooks may also use the action.

Initial tables are Django bootstrap fixtures. They are not the application test/demo data loaded later by container_install.sh.

## Migration hooks

A specification has the form name[,args]. It becomes:

    python manage.py runscript name --script-args args

The first comma separates the script name from one argument string. It is not executed by the shell. Options are repeatable and preserve CLI order. Stage rejects migration-script options.

before_django_migrate and after_django_migrate are separate application callbacks around migrate; they are not the CLI runscript mechanism.

## Application-owned block

Only BEGIN BU-ISCIII APPLICATION: install-hooks through its matching END marker is application-owned.

| Hook | Phase | Purpose |
|---|---|---|
| install_application_system_packages | dependency stage | Install build/system packages. |
| prepare_application_directories | application stage | Prepare application persistent paths. |
| stage_application_custom_files | application stage | Process extra staged files. |
| write_application_runtime_env | application stage | Write an additional runtime environment. |
| validate_application_runtime | bootstrap | Validate runtime integrations. |
| before_django_migrate | bootstrap | Prepare application migrations. |
| after_django_migrate | bootstrap | Perform post-migration setup. |
| set_application_permissions | standard | Apply direct-install permissions. |
| restart_application_server | standard | Reload/restart a direct-install server. |

Lifecycle functions outside this block are managed. Hooks should be idempotent so a failed operation can be retried.

## Configuration and settings

--conf is resolved relative to the script directory, must exist, and is sourced. Non-stage workflows reject active uppercase assignments containing CHANGE_ME. Bootstrap preserves exported DB_HOST, DB_PORT, DB_NAME, DB_USER, and DB_PASSWORD so Compose topology values override standalone file defaults.

For production, container_install.sh renders the host-side settings bind from application-owned conf/template_settings.py through lib/container/django.sh. It copies installation settings into the running container at REPO_PATH/conf/.runtime_install_settings.txt, assigns application ownership, and invokes bootstrap with that path. It removes the temporary file after a production bootstrap attempt; test mode retains it.

install.sh renders Django settings only during stage/standard work when enabled. The renderer preserves an existing non-placeholder SECRET_KEY and substitutes standard and application template values. See [configuration variables](../configuration-variables.md) and the [configuration guide](../../guides/configuration.md).

## Standard workflow

| Scope | Dependencies | Application stage | Bootstrap |
|---|---:|---:|---:|
| full | Yes | Yes | Yes |
| dep | Yes | No | No |
| app | No | Yes | Yes |

Standard mode renders settings by default. It calls restart_application_server afterward unless restart is skipped.

## Failure behavior

The script uses set -euo pipefail. Invalid options/configuration, missing required values, unavailable revisions, dirty source when switching revision, dependency errors, missing staged artifacts, database timeout, Django checks, hooks, migrations, fixtures, collectstatic, and verification failures abort. The exit trap attempts to restore the original Git ref.

There is no automatic filesystem or database rollback. Migration failure can leave the database unchanged, partially migrated, or fully migrated according to Django and application transaction behavior. See the [upgrade and rollback guide](../../guides/upgrades-and-rollback.md).

[container_start.sh](container-start.md) owns repeatable process startup; bootstrap owns deployment-time database work. Migrations do not run on every container restart. Host orchestration, permissions, readiness, and smoke tests belong to [container_install.sh](container-install.md).

## Examples

These are inner-script examples; container deployments normally invoke them through container_install.sh.

    bash install.sh --stage install \
      --conf conf/docker_test_settings.txt \
      --render-settings

    bash install.sh --bootstrap install \
      --conf /path/to/runtime-settings

    bash install.sh --bootstrap upgrade \
      --conf /path/to/runtime-settings \
      --script_after normalize_records,2026
