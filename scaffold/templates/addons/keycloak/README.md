# Keycloak add-on

The assembler follows the PathoCore identity stack and generates both
`keycloak_db` and `keycloak`:

- MySQL health checks and dependency ordering;
- persistent `keycloak_db_data` as the primary identity state;
- Keycloak `start` in production and `start-dev` in test;
- strict production hostname, forwarded proxy headers and HTTP behind Apache;
- a bounded TCP health check with Keycloak's longer startup allowance;
- a reproducible realm-import directory mounted read-only.

Keycloak owns production and test settings under `conf/keycloak/`. Map a
protected production copy with `--install_conf_map keycloak,<path>`.
`CONFIG_SERVICE` still identifies the related application for derived defaults.

The source fragments are
`addons/keycloak/conf/docker_production_settings.txt.tmpl` and
`docker_test_settings.txt.tmpl`. The scaffold renders each as an independent
add-on settings file.

The realm import bind is required but is not the persistent identity store.
Keycloak imports a realm only when it does not already exist, normally on a
fresh database. Normal backup/restore therefore protects `keycloak_db_data` and
the realm source configuration together. Optional provider/theme binds are
shown as commented examples in the Compose fragment.

Permissions remain separate: the realm-import host bind has the Keycloak host
spec, the Keycloak container has an explicit empty writable-mount spec, and the
database volume is repaired by `keycloak_db_running_mount_permission_spec`.
