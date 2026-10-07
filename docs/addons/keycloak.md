# Keycloak addon

## Addon overview

Keycloak is optional identity infrastructure selected through `ADDONS.keycloak`; it is not an application profile. The addon can provide a shared OpenID Connect (OIDC) realm to one or more application services while those services retain their own framework profiles, builds, runtimes, and authentication code.

Before starting a deployment, confirm that the repository's deployment standards are synchronized to the current expected commit or version. If they are not, stop and follow the standards synchronization guideline for the required commit or version, commit the resulting synchronization changes, and then return to the deployment procedure. Run the generated configuration check before starting containers.

## When to use it

Select this addon when the deployment must run a managed Keycloak server and its MySQL database. Do not select it merely because an application uses an external identity provider; the current addon always generates the managed identity stack.

## Generated services

For an application slug such as `example`, the addon generates Compose services named `example-keycloak` and `example-keycloak-db`. The Keycloak service also has the stable `keycloak` alias on `deployment_net`, which application containers use for server-to-server requests. Both services have Compose healthchecks, and Keycloak waits for the database healthcheck to pass before starting.

Keycloak uses `quay.io/keycloak/keycloak:26.6.1`; its database uses `docker.io/library/mysql:8.0`. These versions are defined by the addon templates rather than the project descriptor.

## Configuration ownership

`ADDONS.keycloak.CONFIG_SERVICE` identifies the application service that owns the addon relationship and derived settings in a multi-service deployment. It defaults to the first application service, so a standalone deployment normally does not need to set it. This ownership does not make Keycloak part of that service's profile.

The addon generates its server settings under `conf/keycloak/`. Production installation maps the protected Keycloak settings independently from application settings. Keycloak-prefixed server variables cover database credentials, bootstrap administration, public URL and loopback port, realm import, and SMTP/theme configuration. See the [configuration variable reference](../reference/configuration-variables.md) for the complete dictionary.

## Database and persistence

The generated MySQL service stores the identity platform's authoritative persistent state in the named `keycloak_db_data` volume. Production requires separate database-user and database-root passwords; the database is exposed only to the Compose network. Test mode also uses the named volume so state survives container restarts, but its credentials and data are disposable and the database additionally publishes a loopback-only diagnostic port.

Realm import is not a substitute for backing up the Keycloak database. After initialization, changes made through Keycloak live in the database and must be protected through the deployment's backup and restore procedure.

## OIDC consumers

`ADDONS.keycloak.OIDC_SERVICES` identifies application services that receive the generated OIDC validation contract. The current scaffold accepts only Django services in this array, rejects unknown services, removes duplicates, and defaults to `[CONFIG_SERVICE]` when the configuration owner is Django; otherwise it defaults to an empty array.

Configuration ownership and OIDC consumption are separate concepts. One application can own the addon configuration while one or more Django services consume OIDC settings. Selected consumers receive the OIDC settings and Compose environment. Compose derives `OIDC_ISSUER` as `${KEYCLOAK_PUBLIC_URL}/realms/${KEYCLOAK_REALM}` and `OIDC_JWKS_URL` as `http://keycloak:8080/realms/${KEYCLOAK_REALM}/protocol/openid-connect/certs`, overriding application settings for these two values. Keep audience, client ID, cache duration, request timeout, and the authentication-required flag in each consumer's settings. The configuration checker skips application issuer/JWKS defaults when Compose supplies both managed values.

## Hostname and proxy model

Production requires `KEYCLOAK_PUBLIC_URL`, enables strict hostname handling, accepts `xforwarded` proxy headers, and runs HTTP inside the Compose network. The normal public route may be provided by the Apache addon when selected, while a loopback-only host port remains available for direct diagnostics. The database has no production host port.

Browser-visible issuer values must match the public Keycloak URL exactly, including scheme, host, port, path, realm, and trailing-slash semantics. Container-to-container JWKS and Admin API requests use `http://keycloak:8080`; that internal alias must not replace the public issuer expected in tokens.

## Realm import

The scaffold creates application-managed sources at `conf/keycloak/realm-production.json` and `conf/keycloak/realm-test.json`. Before Compose starts, the installer renders supported environment placeholders into `${KEYCLOAK_IMPORT_PATH}/${KEYCLOAK_REALM}-realm.json`, restricts the generated JSON to mode `0640` with container-compatible ownership, and mounts the import directory read-only at `/opt/keycloak/data/import` with an SELinux relabel option.

Keycloak starts with `--import-realm`, but an import creates a realm only when that realm is absent, normally with a fresh database. It does not continuously synchronize or overwrite an existing realm. The scaffold preserves application-owned values and the contents of the realm's `groups`, `clientScopes`, `clients`, and `users` arrays while adding missing standard properties during standards synchronization.

## Admin access

`ADDONS.keycloak.ADMIN_ACCESS` is a boolean that defaults to `false`. When it is `true`, the scaffold adds the `KEYCLOAK_ADMIN_API_*` Compose environment to the configuration-owning Django service; when it is `false`, those application-side values are omitted. The generated Django settings-file and Python contract is emitted only when that settings owner is also an OIDC consumer.

This option does not publish an additional network port, grant permissions inside Keycloak, create application code, or reuse the server bootstrap account. Applications must supply and protect an appropriate client secret or service-account credentials and implement their own Admin API calls. `KEYCLOAK_ADMIN` and `KEYCLOAK_ADMIN_PASSWORD` are separate bootstrap inputs used only when the server database is empty.

## Health and smoke checks

The MySQL healthcheck runs `mysqladmin ping`; Keycloak waits for it and then uses a TCP connection check against port `8080`. These checks establish process and port readiness, not successful authentication or realm correctness.

The generated post-install guidance requires operators to confirm realm discovery, OIDC token validation, and login/logout, and to test administrative access only when enabled. The scaffold does not currently automate those end-to-end smoke flows or an issuer/discovery HTTP assertion.

## Test and production

| Behavior | Test | Production |
|---|---|---|
| Keycloak command | `start-dev --import-realm` | `start --import-realm` |
| Public URL default | `http://127.0.0.1:8081` | Required explicit URL |
| Hostname strictness | Disabled | Enabled |
| Proxy headers | `xforwarded` | `xforwarded` |
| Keycloak host port | Loopback only, default `8081` | Loopback only, default `8081` |
| Database host port | Loopback only, default `6607` | None |
| Credentials | Disposable defaults | Required protected secrets |
| Realm source | Test realm file | Production realm file |
| Database volume | Restart-persistent but disposable | Critical persistent state |

Test defaults must never be copied into production settings.

## Security considerations

Protect `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_DB_PASSWORD`, `KEYCLOAK_DB_ROOT_PASSWORD`, SMTP credentials, and any `KEYCLOAK_ADMIN_API_*` credentials. Replace all production `CHANGE_ME` values before deployment. Keep the database unexposed, keep the public hostname and OIDC issuer aligned, and preserve strict production hostname handling. The realm import can contain sensitive client data and is deliberately staged with non-public permissions.

## Application integration

For selected Django consumers, the addon supplies configuration values and environment wiring only. The application remains responsible for JWT validation, authorization rules, login or logout flows, client behavior, error handling, and any Admin API implementation. See the [Django profile](../profiles/django.md) and the [configuration variable reference](../reference/configuration-variables.md).

## Backup and restore

Back up the `keycloak_db_data` volume as critical persistent state and retain the protected addon settings and realm source needed to reconstruct the deployment. The repository-generated operational documentation includes database dump/restore commands and should be adapted into the deployment's `LEAME.md`, with ownership assigned to the application team, operations team, or DBA as appropriate. Follow the [backup and restore guide](../guides/backups-and-restore.md); restoring realm JSON alone does not restore users, credentials, sessions, or changes stored in the database.

## Customization boundaries

| Change | Correct location |
|---|---|
| Keycloak credentials and URLs | Protected installation settings |
| Service that owns addon settings | Project descriptor `CONFIG_SERVICE` |
| Django services that consume OIDC | Project descriptor `OIDC_SERVICES` |
| Application access to the Admin API contract | Project descriptor `ADMIN_ACCESS` plus application code |
| Generic Keycloak deployment behavior | `scaffold/templates/addons/keycloak/` |
| Application OIDC and authorization code | Application repository or application profile |
| Realm values, clients, roles, groups, and users | Supported `conf/keycloak/realm-*.json` source |
| Generated Compose, installer, or settings fragments | Do not edit directly; change their source or supported inputs |

Use `ADDONS.keycloak.MOUNTS` to add application-owned provider or theme mounts in test and production. For example, `./keycloak/themes/example:/opt/keycloak/themes/example:ro,z` mounts a theme read-only with shared SELinux relabeling. Operators must choose valid paths, access modes, and relabel options. Changes to generic addon behavior belong upstream in the deployment standards; deployment-specific realm and application behavior belong in the application repository.
