# MySQL support

## Overview

MySQL is supporting deployment infrastructure, not an independently selectable application profile or `ADDONS.mysql` addon. The selectable application profiles are django, nextjs, and react-vite. MySQL is generated as a Django-owned supporting Compose service when required by the deployment mode and the Django service's DATABASE descriptor setting. This page lives in the addon catalog because it documents supporting infrastructure rather than application build and runtime behavior.

Django is not required to use a generated database. Production may connect to external database infrastructure instead.

## When MySQL is generated

SERVICES.<name>.DATABASE is accepted only for Django services. Its supported values are:

| Value | Test topology | Production topology |
|---|---|---|
| external | Generates a local MySQL service for the test deployment. | Generates no database container; Django uses the configured external endpoint. |
| compose | Generates a local MySQL service for the test deployment. | Generates a private MySQL service and persistent named volume. |

external is the descriptor default. The test topology always includes SERVICE-db so local testing does not depend on production infrastructure. See the [project descriptor reference](../reference/project-descriptor.md).

## Generated Compose service

The service name is the Django application service name followed by -db. For an application service named registry, the generated database service is registry-db.

| Property | Test | Production DATABASE=compose |
|---|---|---|
| Image | docker.io/library/mysql:8.0 | docker.io/library/mysql:8.0 |
| Network | deployment_net | deployment_net |
| Data path | /var/lib/mysql | /var/lib/mysql |
| Volume | SERVICE_test_db | SERVICE_db_data |
| Root initialization | MYSQL_ROOT_PASSWORD from DB_ROOT_PASSWORD | MYSQL_RANDOM_ROOT_PASSWORD=yes |
| Application database/user | MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD | Same |
| Authentication option | Image default | --default-authentication-plugin=mysql_native_password |
| Restart policy | No explicit policy in the generated test fragment | unless-stopped |
| Host port | Not published | Not published; port 3306 is exposed only inside the container network |

The official image entrypoint initializes the named database and application user from these environment values when the data directory is new. The scaffold does not implement separate SQL user/grant commands.

## Configuration

The Django installation settings provide:

- DB_HOST and DB_PORT for the address Django uses;
- DB_NAME for the application database;
- DB_USER and DB_PASSWORD for the application account; and
- DB_ROOT_PASSWORD for the generated test database's root initialization.

In generated test Compose, DB_HOST is the SERVICE-db Compose identity. In production DATABASE=compose, operators configure DB_HOST for that generated service and port 3306. In production external mode, DB_HOST and DB_PORT identify the separately managed database.

The application connects with DB_USER and DB_PASSWORD, not the root account. In production Compose mode, the root password is randomized by the official image and is not supplied to Django. The scaffold delegates initial database/user creation and grants to the official MySQL image behavior.

See [configuration variables](../reference/configuration-variables.md) for sensitivity and the complete Django settings model.

## Connectivity

    Django container
          |
          +-- generated DB -> SERVICE-db:3306 on deployment_net
          |
          +-- external DB  -> DB_HOST:DB_PORT outside generated topology

Compose service names are internal DNS identities. They are not public hostnames and are not intended for browser or external-client access.

The Django service depends on SERVICE-db reaching healthy state in generated test deployments and in production when DATABASE=compose. External mode has no generated database dependency; Django bootstrap performs its own bounded database connectivity check before migrations.

## Persistence and permissions

Both generated database modes mount a named volume at /var/lib/mysql. Recreating the container with Compose up --force-recreate does not intentionally remove that volume. Test uses SERVICE_test_db; production Compose uses SERVICE_db_data.

A test volume is test-oriented but is not automatically deleted after a run. It can preserve state across container recreation until the operator explicitly removes it.

For production Compose databases, the generated installer includes SERVICE-db in permission services and applies UID/GID 999:999 with owner/group read-write permissions to /var/lib/mysql inside the running container. This supports restored or moved named-volume data. Operators should use the shared permission workflow rather than guessing an engine-specific host volume path.

Rootless Podman may map container IDs through a user namespace, but the database uses an engine-managed named volume rather than a documented host directory. Docker and Podman volume storage paths are not an operational interface.

Persistent storage is not a backup. A named volume protects data from ordinary container replacement but not deletion, corruption, failed migration, host loss, or an invalid database upgrade.

## Health and application readiness

The generated healthchecks use mysqladmin ping against 127.0.0.1 inside the database container:

- test authenticates as root with MYSQL_ROOT_PASSWORD every 5 seconds, with a 5-second timeout and 20 retries;
- production Compose authenticates as MYSQL_USER with MYSQL_PASSWORD every 10 seconds, with a 5-second timeout, 30 retries, and a 30-second start period.

A healthy result shows that the MySQL server accepts the configured ping. It does not prove that Django migrations are complete, application queries are correct, data is intact, or backups can be restored.

The generated smoke script has no MySQL-specific fragment. Django's bootstrap and smoke behavior remain separate: bootstrap waits for connectivity and applies migrations; the Django smoke fragment checks Django and migration-plan output.

## Test and production summary

| Area | Test | Production |
|---|---|---|
| Generation | Always for Django | Only when DATABASE=compose |
| Alternative | None in generated test topology | DATABASE=external |
| Credentials | Disposable settings including DB_ROOT_PASSWORD | Protected application credentials; random root password for Compose DB |
| Storage | SERVICE_test_db named volume | SERVICE_db_data named volume, or infrastructure-owned external storage |
| Port exposure | Compose network only | Compose network only, or external infrastructure policy |
| Lifecycle | Created for test topology; data remains until volume removal | Persistent supporting service with unless-stopped, or externally operated |

## Backups and restore

A production Compose-managed database must be included in deployment backup and restore planning. An external database's backup owner may instead be the infrastructure or DBA team, but that ownership and procedure must be explicit.

Copying the files of a running /var/lib/mysql volume is not automatically a valid logical backup. The repository's backup guide uses MySQL/MariaDB logical dumps for the generated database examples. Record the application-specific backup, verification, retention, and restore commands in LEAME.md and test restoration before relying on them.

See [backups and restore](../guides/backups-and-restore.md).

## Security and version management

Production database passwords belong in protected, ignored installation settings. Do not reuse disposable test values in production. The Django application should use its application account rather than an administrative account.

The generated Compose database is private to deployment_net and has no host port mapping. If separate infrastructure exposes MySQL, that exposure and access policy are outside this generated support model.

The image tag is pinned in the Django Compose fragments as mysql:8.0 rather than latest. Changing the database major version is a database upgrade operation requiring compatibility review, backup, and tested migration/rollback procedures; it is not an ordinary application image refresh.

No additional TLS, encryption-at-rest, character-set, collation, replication, or high-availability configuration is generated. Applications or infrastructure that require those properties must document and own them rather than assuming this support component supplies them.

## Customization boundaries

| Change | Correct owner |
|---|---|
| Database credentials and external host/port | Protected installation settings |
| Compose-managed versus external production DB | SERVICES.<name>.DATABASE in the project descriptor |
| Generic generated MySQL service behavior | Django support fragments under scaffold/templates/profiles/django/compose/ |
| Django database settings | Django application template/profile |
| Schema and data migrations | Application migrations and Django bootstrap |
| Backup schedule, retention, monitoring, and external DB operation | Deployment/infrastructure operations |
| Generated Compose service | Do not edit directly |

There is currently no `scaffold/templates/profiles/mysql/` or `scaffold/templates/addons/mysql/` implementation directory, standalone `mysql` `PROFILE` value, or `ADDONS.mysql` selector. A reusable change to generated MySQL behavior belongs with the Django-owned supporting fragments unless the architecture is deliberately changed.

## Relationship with Django

The Django settings renderer places DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, and connection lifetime into the rendered settings. Compose may override the database endpoint supplied during bootstrap so a combined topology uses its selected service identity.

Database server startup belongs to MySQL; schema evolution belongs to [Django bootstrap](../profiles/django.md). MySQL health, Django connectivity, migration completion, and application acceptance are distinct checks.

## Further reading

- [MySQL 8.0 Reference Manual](https://dev.mysql.com/doc/refman/8.0/en/)
- [Official MySQL container image](https://hub.docker.com/_/mysql)
- [Docker Compose guide](../guides/docker-compose.md)
