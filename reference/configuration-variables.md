# Configuration variables

Before starting a deployment, confirm that the generated project is fully
synchronized with the current deployment standards. If it is not, stop and follow the synchronization guidance for the applicable standards commit and/or version; return to the deployment only after synchronization is complete. See [Upgrades and rollback](../guides/upgrades-and-rollback.md) and [Deployment workflow](../guides/deployment-workflow.md).

This is the central reference for profile and addon settings. Values belong in the test or production `INSTALL_SETTINGS` file. “Required” means required when the profile, addon, or capability is selected. Never commit sensitive values.

## Common application variables

| Variables | Modes | Required | Sensitive | Purpose / timing |
|---|---|---:|---:|---|
| `REPO_PATH`, `INSTALL_PATH` | test, prod | Yes | No | Install-time source and destination paths. |
| `APP_UID`, `APP_GID` | test, prod | Yes | No | Runtime file-owner IDs. |
| `APP_PORT` | test, prod | Yes | No | Container port and default proxy upstream port. |

## Django

| Variables | Modes | Required | Sensitive | Purpose / timing |
|---|---|---:|---:|---|
| `PROJECT_MODULE`, `PYTHON_BIN_PATH`, `APP_SHELL` | test, prod | Yes | No | Startup package, interpreter, and shell. |
| `REQUIRED_MODULES`, `MIGRATION_MODULES` | test, prod | Yes | No | Startup import and migration checks. |
| `HOST_LOG_PATH`, `DJANGO_SETTINGS_PATH` | test, prod | Yes | No | Host logs and generated runtime environment path. |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` | test, prod | Yes | No | Database connection. |
| `DB_PASSWORD`, `DB_ROOT_PASSWORD` | test, prod | Yes | Yes | Application and administrator DB credentials. |
| `DJANGO_DEBUG` | test, prod | Yes | No | Debug switch; production must be false. |
| `DJANGO_SECRET_KEY` | test, prod | Yes | Yes | Cryptographic signing secret. |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | test, prod | Yes | No | Host and CSRF-origin policy. |
| `DB_CONN_MAX_AGE` | test, prod | Yes | No | Persistent connection lifetime. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` | test, prod | Yes | No | SMTP transport. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | test, prod | Yes | Yes | SMTP credentials; may be empty without SMTP auth. |
| `CREATE_INITIAL_SUPERUSER` | test, prod | Yes | No | Enables guarded initial-user creation. |
| `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` | test, prod | Conditional | Yes | Initial account when creation is enabled. |
| `WEB_CONCURRENCY`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`, `GUNICORN_KEEPALIVE` | test, prod | Yes | No | Gunicorn sizing and timeouts. |
| `APP_START_WAIT_TIMEOUT_SECONDS` | test, prod | Yes | No | Startup readiness timeout. |
| `LOG_TYPE`, `LOG_PATH` | test, prod | Yes | No | Runtime logging. |

### Optional Django capabilities

| Variables | Capability | Modes | Required | Sensitive | Purpose |
|---|---|---|---:|---:|---|
| `API_CORS_ALLOWED_ORIGINS`, `API_THROTTLE_RATE`, `API_DOCS_REQUIRE_STAFF` | API | test, prod | Yes | No | CORS, throttling, and docs access. |
| `OIDC_AUTH_REQUIRED`, `OIDC_ISSUER`, `OIDC_JWKS_URL`, `OIDC_AUDIENCE`, `OIDC_CLIENT_ID` | Keycloak OIDC | test, prod | Yes | No | Token authentication and identity. |
| `OIDC_JWKS_CACHE_TTL_SECONDS`, `OIDC_JWKS_TIMEOUT_SECONDS` | Keycloak OIDC | test, prod | Yes | No | JWKS cache/request timeouts. |
| `KEYCLOAK_ADMIN_API_BASE_URL`, `KEYCLOAK_ADMIN_API_REALM`, `KEYCLOAK_ADMIN_API_TOKEN_REALM`, `KEYCLOAK_ADMIN_API_CLIENT_ID` | Admin API | test, prod | Yes | No | Endpoint and client context. |
| `KEYCLOAK_ADMIN_API_CLIENT_SECRET`, `KEYCLOAK_ADMIN_API_USERNAME`, `KEYCLOAK_ADMIN_API_PASSWORD` | Admin API | test, prod | Yes | Yes | Privileged credentials. |
| `KEYCLOAK_ADMIN_API_TIMEOUT_SECONDS`, `KEYCLOAK_ADMIN_API_SEND_ACTION_EMAILS`, `KEYCLOAK_ADMIN_API_ACTION_EMAIL_REDIRECT_URI` | Admin API | test, prod | Yes | No | Request and action-email behavior. |

## Browser profiles

| Variables | Profile | Modes | Required | Sensitive | Purpose / timing |
|---|---|---|---:|---:|---|
| `VITE_API_BASE_URL` | React | test, prod | Yes | No; public | Build-time browser API URL. |
| `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SECOND_API_BASE_URL` | Next.js | test, prod | Yes | No; public | Build-time browser API URLs. |
| `NEXT_PUBLIC_KEYCLOAK_URL`, `NEXT_PUBLIC_KEYCLOAK_REALM`, `NEXT_PUBLIC_KEYCLOAK_CLIENT_ID` | Next.js | test, prod | Yes | No; public | Browser Keycloak configuration. |
| `NEXT_PUBLIC_USE_CASE_DATA_MODE`, `NEXT_PUBLIC_USE_CASE_ALERTS_CONTACT_EMAIL` | Next.js | test, prod | Yes | No; public | Browser feature configuration. |
| `PATHOCORE_API_PROXY_TARGET`, `MEPRAM_OMOP_API_PROXY_TARGET` | Next.js | test, prod | Yes | No | Runtime server proxy targets. |
| `AUTH_SECRET` | Next.js | test, prod | Yes | Yes | Server authentication/session secret. |
| `AUTH_URL`, `AUTH_TRUST_HOST`, `NEXTAUTH_URL` | Next.js | test, prod | Yes | No | Server authentication routing. |

`VITE_*` and `NEXT_PUBLIC_*` values ship to browsers; never put secrets in
them.

## Apache addon

| Variables | Modes | Required | Sensitive | Purpose / timing |
|---|---|---:|---:|---|
| `APACHE_CONF_PATH`, `APACHE_LOG_PATH` | test, prod | Yes | No | Compatibility config input and host logs. |
| `APACHE_BIND_HOST`, `APACHE_PORT`, `APACHE_SERVER_NAME` | test, prod | Yes | No | Published listener and virtual host. |
| `APACHE_UPSTREAM_SERVICE` | test, prod | No | No | Empty derives from `CONFIG_SERVICE`. |
| `APACHE_UPSTREAM_PORT` | test, prod | No | No | Empty derives from selected `APP_PORT`. |
| `APACHE_PROXY_TIMEOUT` | test, prod | No | No | Empty derives from `GUNICORN_TIMEOUT`, then `120`. |
| `APACHE_LOG_STEM` | test, prod | No | No | Empty derives from `APACHE_SERVER_NAME`. |
| `APACHE_SERVER_STATUS_SERVER_NAME`, `APACHE_SERVER_STATUS_SERVER_ALIASES`, `APACHE_SERVER_STATUS_ALLOW_FROM` | test, prod | Yes | No | Status host and allow list. |
| `APACHE_FORWARDED_PROTO`, `APACHE_FORWARDED_PORT`, `APACHE_LIMIT_REQUEST_BODY` | test, prod | Yes | No | Forwarding metadata and body limit. |

Commented `APACHE_SECOND_*` entries are inactive application-owned examples.

## Keycloak addon

| Variables | Modes | Required | Sensitive | Purpose / timing |
|---|---|---:|---:|---|
| `KEYCLOAK_DB_NAME`, `KEYCLOAK_DB_USER` | test, prod | Yes | No | Database identity. |
| `KEYCLOAK_DB_PASSWORD`, `KEYCLOAK_DB_ROOT_PASSWORD` | test, prod | Yes | Yes | Database credentials. |
| `KEYCLOAK_DB_PORT_HOST` | test only | Yes | No | Test DB host publication. |
| `KEYCLOAK_PUBLIC_URL`, `KEYCLOAK_PORT` | test, prod | Yes | No | Public URL and port. |
| `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD` | test, prod | Yes | Yes | Bootstrap administrator credentials. |
| `KEYCLOAK_REALM_TEMPLATE_PATH`, `KEYCLOAK_REALM`, `KEYCLOAK_IMPORT_PATH` | test, prod | Yes | No | Realm source, name, and generated import. |
| `KEYCLOAK_SMTP_HOST`, `KEYCLOAK_SMTP_PORT` | test, prod | Yes | No | SMTP endpoint. |
| `KEYCLOAK_SMTP_FROM`, `KEYCLOAK_SMTP_FROM_DISPLAY_NAME`, `KEYCLOAK_SMTP_REPLY_TO`, `KEYCLOAK_SMTP_REPLY_TO_DISPLAY_NAME`, `KEYCLOAK_SMTP_ENVELOPE_FROM` | test, prod | Yes | No | Email identities. |
| `KEYCLOAK_SMTP_AUTH`, `KEYCLOAK_SMTP_SSL`, `KEYCLOAK_SMTP_STARTTLS`, `KEYCLOAK_SMTP_ALLOW_UTF8` | test, prod | Yes | No | SMTP switches. |
| `KEYCLOAK_SMTP_CONNECTION_TIMEOUT`, `KEYCLOAK_SMTP_TIMEOUT`, `KEYCLOAK_SMTP_WRITE_TIMEOUT` | test, prod | Yes | No | SMTP timeouts. |
| `KEYCLOAK_SMTP_USER`, `KEYCLOAK_SMTP_PASSWORD` | test, prod | Yes | Yes | May be empty when SMTP auth is disabled. |
| `KEYCLOAK_EMAIL_THEME` | test, prod | Yes | No | Realm email theme. |

## Other addons

| Variables | Addon | Modes | Required | Sensitive | Purpose / timing |
|---|---|---|---:|---:|---|
| `NEXTSTRAIN_IMAGE`, `NEXTSTRAIN_BUILD_CONTEXT`, `NEXTSTRAIN_DOCKERFILE` | Nextstrain | test, prod | Yes | No | Runtime image and build inputs. |
| `NEXTSTRAIN_PORT`, `NEXTSTRAIN_HOST_PORT`, `NEXTSTRAIN_DATA_DIR` | Nextstrain | test, prod | Yes | No | Ports and host data. |
| `NEXTSTRAIN_MAPBOX_ACCESS_TOKEN`, `NEXTSTRAIN_MAPBOX_STYLE_OWNER`, `NEXTSTRAIN_MAPBOX_STYLE_ID` | Nextstrain | test, prod | Yes | No; public | Browser Mapbox configuration. |
| `SAMBA_USER`, `SAMBA_PASSWORD` | Samba | test only | Yes | Yes | Test share credentials; production has no settings. |

## Ownership, derivation, and validation

Multi-service application settings use a normalized service prefix: uppercase,
with non-alphanumeric characters replaced by `_` (for example,
`clinical-api` → `CLINICAL_API_APP_PORT`). Addons retain their own namespace.
`CONFIG_SERVICE` selects the application that supplies an addon's topology
context; it does not transfer ownership of addon settings.

The installer derives `GIT_REVISION` from the source revision and
`<PREFIX>_IMAGE` from each built image. Apache's operator-visible derivations
are listed above. Internal temporary and Compose plumbing variables are omitted
because operators neither set nor consume them.

- Test and production use separate `INSTALL_SETTINGS` files.
- Run the configuration check before deployment. Production rejects every
  active uppercase assignment containing the exact `CHANGE_ME` marker. It
  reports the key and redacts sensitive values; comments are inactive.
- Empty is valid only where a profile/addon permits it or defines a derivation.
- Generated environment files are atomic, mode `0600`; invalid names,
  duplicates, and multiline values are rejected.
- Public means browser-visible, not secret. Keep all secrets out of Git.

See [Configuration](../guides/configuration.md),
[Docker Compose](../guides/docker-compose.md), and
[`container-install.sh`](scripts/container-install.md).
