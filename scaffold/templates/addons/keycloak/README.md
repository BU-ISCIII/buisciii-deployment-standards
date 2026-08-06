# Keycloak add-on

The assembler follows the PathoCore identity stack and generates both
`keycloak_db` and `keycloak`:

- MySQL health checks and dependency ordering;
- persistent `keycloak_db_data` as the primary identity state;
- Keycloak `start` in production and `start-dev` in test;
- strict production hostname, forwarded proxy headers and HTTP behind Apache;
- a bounded TCP health check with Keycloak's longer startup allowance;
- a reproducible realm-import directory mounted read-only.

Keycloak does not introduce another installation-settings file. Its
`KEYCLOAK_*` section lives in one selected application's production/test
settings. A standalone project selects its only service automatically; a
multi-app project uses `ADDONS.keycloak.CONFIG_SERVICE` when the first service
is not the desired owner. The section documents database/admin secrets, public
URL, diagnostic ports and realm-import path together.

The realm import bind is required but is not the persistent identity store.
Keycloak imports a realm only when it does not already exist, normally on a
fresh database. Normal backup/restore therefore protects `keycloak_db_data` and
the realm source configuration together. Optional provider/theme binds are
shown as commented examples in the Compose fragment.

Permissions remain separate: the realm-import host bind has the Keycloak host
spec, the Keycloak container has an explicit empty writable-mount spec, and the
database volume is repaired by `keycloak_db_running_mount_permission_spec`.
