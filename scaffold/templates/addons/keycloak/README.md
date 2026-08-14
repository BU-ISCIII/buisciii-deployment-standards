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

The repository-owned realm source is copied into a deployment-owned bind under
`/srv/containers/bind/<application>/keycloak/realm-import` for production.
The installer creates this child directory automatically when the application
bind root is writable by the deployment user; hardened hosts may pre-create it
with the same deployment ownership.
Keycloak imports a realm only when it does not already exist, normally on a
fresh database. Normal backup/restore therefore protects `keycloak_db_data` and
the staged realm configuration together. Optional provider/theme binds are
shown as commented examples in the Compose fragment.

Permissions remain separate: staged realm files are owned by Keycloak UID/GID
`1000:0` with mode `0640`, the Keycloak container has an explicit empty
writable-mount spec, and the database volume is repaired separately.
