# Keycloak add-on

The assembler follows the PathoCore identity stack and generates both
`keycloak_db` and `keycloak`:

- MySQL health checks and dependency ordering;
- persistent `keycloak_db_data` as the primary identity state;
- Keycloak `start` in production and `start-dev` in test;
- strict production hostname, forwarded proxy headers and HTTP behind Apache;
- a bounded TCP health check with Keycloak's longer startup allowance;
- a reproducible realm-import directory mounted read-only.

`ADDONS.keycloak.INSTALL_CONF` and `TEST_INSTALL_CONF` are required. Settings
use unprefixed source keys (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `PUBLIC_URL`,
`ADMIN`, `ADMIN_PASSWORD`, `IMPORT_PATH`, etc.); the environment writer prefixes
them with `KEYCLOAK_` in the assembled Compose contract.

The realm import bind is required but is not the persistent identity store.
Keycloak imports a realm only when it does not already exist, normally on a
fresh database. Normal backup/restore therefore protects `keycloak_db_data` and
the realm source configuration together. Optional provider/theme binds are
shown as commented examples in the Compose fragment.

Permissions remain separate: the realm-import host bind has the Keycloak host
spec, the Keycloak container has an explicit empty writable-mount spec, and the
database volume is repaired by `keycloak_db_running_mount_permission_spec`.
