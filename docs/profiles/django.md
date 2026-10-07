# Django deployment profile

## Overview

Selecting the django profile adds the Python/Django image, dependency and source staging, Django settings rendering, runtime startup, database topology integration, migration bootstrap, static and document storage, health wiring, and Django-specific smoke checks.

The profile does not include Apache, Keycloak, or application-specific behavior. Those remain optional addons or application-owned configuration.

## Generated artifacts

| Path | Purpose | Ownership |
|---|---|---|
| Dockerfile | Builds the staged Django runtime image. | Profile-managed |
| install.sh | Stages dependencies/source and performs runtime bootstrap. | Profile-managed with the application-owned install-hooks block |
| scripts/container_start.sh | Starts the repeatable runtime process. | Profile-managed |
| conf/template_settings.py | Source for rendered Django settings. | Application-owned; required renderer structure is checked |
| conf/urls.py | Root URL configuration including the required deployment health route. | Managed structure with application-owned import and route blocks |
| conf/docker_test_settings.txt | Safe, disposable test installation settings. | Generated template; application values must remain non-sensitive |
| conf/docker_production_settings.txt | Production settings template copied to a protected file by the operator. | Generated template; real secrets are not committed |
| conf/INSTALL_SETTINGS.md | Generated variable matrix plus application-owned notes. | Managed with marked application blocks |
| deployment_health/ | Minimal health URL and view used by orchestration. | Profile-managed |
| .github/DJANGO_MIGRATIONS.md | Migration policy for application development. | Profile-managed |

Common files such as container_install.sh, Compose files, smoke_test.sh, README.md, and LEAME.md are assembled by the common scaffold with Django-owned fragments. See the [generated project structure](../reference/generated-project-structure.md).

## Image build and staging

The generated image uses UBI 9 minimal with the configured Python version. It installs the tools needed to stage the application, downloads Supercronic for supported CPU architectures, copies the repository and runtime entrypoint, and invokes install.sh --stage install.

Staging validates Python and required source files, installs application system dependencies through the application hook, creates the virtual environment, installs conf/requirements.txt, copies the application into INSTALL_PATH, generates the Django project wrapper, installs the health-aware URL configuration, and records the deployed revision. The final image runs as the configured non-root APP_UID:APP_GID identity.

Test builds use committed disposable installation settings and render settings.py during the image build. Production builds mount the protected installation settings as an ephemeral build secret and explicitly disable settings rendering during staging. Production settings and secrets therefore do not remain in the image layer.

See the [install.sh reference](../reference/scripts/install.md) for the exact stage sequence and failure boundaries.

## Django settings

conf/template_settings.py defines application Django structure: installed applications, middleware, templates, database engine, authentication, static/media paths, email, scheduler settings, and project-specific options. The scaffold treats this file as application-owned, but its checker requires the structural placeholders used by the renderer and reports incompatible drift.

Application developers add Django-specific configuration to this template and add matching values to both installation-settings templates and their documentation. They should not add application rules to lib/container/django.sh. That shared profile library validates values, preserves an existing non-placeholder SECRET_KEY, substitutes standard and application tokens, and atomically renders settings.py.

### Production

Before Compose starts the service, container_install.sh renders settings.py on the host from conf/template_settings.py and the selected protected production installation settings. DJANGO_SETTINGS_PATH is bind-mounted at INSTALL_PATH/PROJECT_MODULE/settings.py. The host file is re-rendered on each install or upgrade while an existing generated SECRET_KEY is preserved.

The production build receives the installation settings only through the build-secret mount required for staging inputs. It does not render production settings into the image. During bootstrap, the outer installer also stages a temporary protected installation-settings file inside the running container and removes it after the production bootstrap attempt.

### Test

The test image renders settings.py from conf/docker_test_settings.txt during staging. These values are intended to be disposable and non-sensitive. Test Compose does not use the production settings bind mount.

## Runtime startup

scripts/container_start.sh waits up to the configured timeout for manage.py and the virtualenv activation script, activates the virtual environment, prepares cron and temporary directories, and optionally generates Supercronic jobs from Django CRONJOBS.

Test Compose sets APP_MODE=dev and starts Django runserver with the reloader disabled. Production sets APP_MODE=prod and starts Gunicorn on APP_PORT. WEB_CONCURRENCY overrides worker selection; otherwise the script chooses two workers for up to two CPUs and four workers above that. The final web process is executed with exec so it receives container signals directly.

Startup does not run migrations or fixtures. See the [container_start.sh reference](../reference/scripts/container-start.md).

## Bootstrap and migrations

container_install.sh starts the topology, waits for the profile readiness contract, repairs declared mounts, and then invokes install.sh --bootstrap with install or upgrade.

Bootstrap runs in this order:

1. require the staged manage.py and virtual environment;
2. wait for database connectivity;
3. run the application runtime-validation hook;
4. run Django check --deploy;
5. run requested pre-migration scripts;
6. reject model changes without committed migration files;
7. run the application pre-migrate hook;
8. run migrate --noinput;
9. load the initial fixture when enabled;
10. run requested post-migration scripts;
11. run the application post-migrate hook;
12. run collectstatic --noinput; and
13. verify that the migration plan has no unapplied entries.

A fresh install loads conf/first_install_tables.json by default when the file exists unless tables are skipped. Upgrade does not load it unless explicitly requested. This fixture mechanism is separate from application test/demo data loaded by container_install.sh.

Migrations are deployment-time bootstrap operations. Normal container restarts only execute container_start.sh and do not migrate the database. See the [container installer reference](../reference/scripts/container-install.md).

## Database model

The descriptor field SERVICES.<name>.DATABASE is valid only for Django services and accepts:

| Value | Production behavior |
|---|---|
| external | Default. Generates no production database service; DB_HOST and related settings identify the operator-managed MySQL endpoint. |
| compose | Generates a private service named SERVICE-db using MySQL 8.0 and a persistent SERVICE_db_data volume. The database port is exposed only to the Compose network. |

Test mode always generates a disposable SERVICE-db MySQL 8.0 service backed by SERVICE_test_db, regardless of the production choice. Django waits on its healthy state before the test application starts.

The generated template uses django.db.backends.mysql. Database creation, production credentials, backups, and restore remain operational responsibilities; see the [configuration reference](../reference/configuration-variables.md) and [backup guide](../guides/backups-and-restore.md).

## Persistent data and writable paths

| Data | Test | Production |
|---|---|---|
| Database | SERVICE_test_db named volume | External infrastructure, or SERVICE_db_data when DATABASE=compose |
| Uploaded/documents data | SERVICE_test_documents named volume | SERVICE_documents named volume |
| Collected static files | SERVICE_test_static named volume | SERVICE_static named volume |
| Logs | Image/runtime path | Host bind from HOST_LOG_PATH |
| Rendered settings.py | Stored in the test image | Protected host bind from DJANGO_SETTINGS_PATH |

The profile creates INSTALL_PATH/logs, documents, static, cron, and tmp while staging. The installer applies declared ownership and modes to mounted logs, documents, static files, and production settings. Applications may add their own persistent paths only through the documented topology and permission extension points.

collectstatic populates the static volume during every install and upgrade bootstrap. documents is Django MEDIA_ROOT; the standard does not define application-specific upload models or retention rules.

When the Apache addon is selected, it may mount the Django static and documents volumes read-only and proxy requests to the application. That is addon integration, not core Django behavior.

## Health, readiness, and acceptance

| Mechanism | Django behavior |
|---|---|
| HTTP healthcheck | GET /health/ returns a minimal JSON response without querying external dependencies. |
| Installer readiness | Requires the application container to run and INSTALL_PATH/manage.py to exist. |
| Smoke profile check | Runs manage.py check and checks showmigrations output for unapplied entries. |
| Common smoke check | Requests http://127.0.0.1:APP_PORT/health/ from the deployment host. |

Readiness proves the staged artifact is available, not that bootstrap or a user workflow succeeded. The health endpoint proves the HTTP process responds, not database or external-service availability. See the [smoke-test reference](../reference/scripts/smoke-test.md) for exact guarantees and its documented showmigrations pipeline limitation.

## Configuration decisions

Application maintainers must define:

- repository and installation paths, runtime UID/GID, port, required modules, and migration modules;
- production SECRET_KEY, DEBUG, allowed hosts, CSRF trusted origins, and any API CORS settings;
- external or Compose production database topology and connection values;
- SMTP behavior when application workflows send email;
- Gunicorn workers, threads, timeouts, and startup wait;
- initial administrator policy;
- application-specific Django settings and renderer tokens;
- persistent application paths beyond the generated documents/static/log locations; and
- scheduler jobs, identity integration, and acceptance checks required by the application.

The full variable dictionary is in [configuration variables](../reference/configuration-variables.md). File preparation and secret handling are covered by the [configuration guide](../guides/configuration.md).

Production SECRET_KEY and credentials are sensitive. DEBUG must use the safe production value supplied by configuration. ALLOWED_HOSTS, CSRF/CORS policy, and optional trusted-proxy settings must match the real topology. Internal Compose addresses and browser/public URLs are different configuration scopes.

## Application customization

Supported application-owned areas are:

- conf/template_settings.py for Django settings structure and project-specific renderer tokens;
- marked django-url-imports and django-url-routes blocks in conf/urls.py;
- the install-hooks block in install.sh for application system packages, staged files/directories, runtime validation, migration callbacks, direct-install permissions, and restart behavior;
- the deployment-hooks block in container_install.sh for application test/demo data and application-only permission paths;
- marked application sections in configuration documentation and ignore files; and
- the Django application source and committed migrations.

Do not edit deployment/lib/container/django.sh, managed lifecycle code, generated Compose fragments, health implementation, or profile callbacks locally. Reusable Django-profile changes belong under scaffold/templates/profiles/django/.

## Test and production summary

| Area | Test | Production |
|---|---|---|
| Settings | Committed non-sensitive settings rendered during build | Protected settings rendered on host and bind-mounted at runtime |
| Build configuration | Uses conf/docker_test_settings.txt directly | Uses an ephemeral build secret; settings rendering is disabled in the image |
| Database | Always disposable Compose MySQL | External by default; optional private Compose MySQL |
| Server | Django runserver with no reloader | Gunicorn |
| Published application port | All host interfaces | Host loopback |
| Logs | No host log bind in the generated service | HOST_LOG_PATH bind |
| Initial fixture | Fresh install default when file exists | Same bootstrap rule; production demo/test data is never implicit |

## Optional integrations

[Apache](../addons/apache.md) can provide reverse proxying and read-only access to generated static/document volumes. [Keycloak](../addons/keycloak.md) can supply OIDC and optional admin-API configuration when selected. Neither addon is part of the Django profile itself.

## Further reading

- [Django deployment checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- [Django settings](https://docs.djangoproject.com/en/stable/topics/settings/)
- [Django static files deployment](https://docs.djangoproject.com/en/stable/howto/static-files/deployment/)
