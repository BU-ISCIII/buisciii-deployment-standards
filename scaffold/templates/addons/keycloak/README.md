# Keycloak add-on

The assembler generates a complete identity stack, both `keycloak_db` and `keycloak`:

- MySQL health checks and dependency ordering;
- persistent `keycloak_db_data` as the primary identity state;
- Keycloak `start` in production and `start-dev` in test;
- strict production hostname, forwarded proxy headers and HTTP behind Apache;
- a bounded TCP health check with Keycloak's longer startup allowance;
- a reproducible realm-import directory mounted read-only.

Keycloak owns production and test settings under `conf/keycloak/`. Map a protected production copy with `--install_conf_map keycloak,<path>`. `CONFIG_SERVICE` still identifies the related application for derived defaults. The selected application's settings also expose a generic `KEYCLOAK_ADMIN_API_*` contract for optional realm/user administration. Those credentials are application runtime inputs and are intentionally distinct from the add-on's `KEYCLOAK_ADMIN` server-bootstrap account. Set `ADDONS.keycloak.ADMIN_ACCESS` to `true` to generate that application-side contract. It defaults to `false`, so OIDC-only applications do not receive unused administration settings or Compose variables.

For each service in `OIDC_SERVICES`, Compose derives `OIDC_ISSUER` from
`KEYCLOAK_PUBLIC_URL` and `KEYCLOAK_REALM`, and uses the internal
`keycloak:8080` service for `OIDC_JWKS_URL`. Keep `OIDC_AUDIENCE` and
`OIDC_CLIENT_ID` in each API's settings.

The source fragments are
`addons/keycloak/conf/docker_production_settings.txt.tmpl` and
`docker_test_settings.txt.tmpl`. The scaffold renders each as an independent
add-on settings file.

The repository-owned production or test realm template is rendered into a deployment-owned bind under `/srv/containers/bind/<application>/keycloak/realm-import` for production. Templates use `${UPPER_CASE_VARIABLE}` only as JSON string content. The shared installer escapes those values and does not require an application-side Python realm generator. The installer creates this child directory automatically when the application bind root is writable by the deployment user; hardened hosts may pre-create it with the same deployment ownership. Keycloak imports a realm only when it does not already exist, normally on a fresh database. Normal backup/restore therefore protects `keycloak_db_data` and the staged realm configuration together. Optional provider/theme binds are shown as commented examples in the Compose fragment.

Set `ADDONS.keycloak.MOUNTS` when the application supplies a Keycloak theme or
provider. The value is a complete read-only Compose mount such as
`./keycloak/themes/example:/opt/keycloak/themes/example:ro,z`; use `:z` on
SELinux hosts when the source is shared only with this container.

Permissions remain separate: staged realm files are owned by Keycloak UID/GID
`1000:0` with mode `0640`, the Keycloak container has an explicit empty
writable-mount spec, and the database volume is repaired separately.

The scaffold manages the required object-property schema of `conf/keycloak/realm-production.json` and `realm-test.json`. Applications own the scalar values and the contents of `groups`, `clientScopes`, `clients`, and `users`; synchronization adds missing standard properties without replacing those application-specific arrays.
