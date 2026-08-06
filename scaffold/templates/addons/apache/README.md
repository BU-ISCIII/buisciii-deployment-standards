# Apache add-on

The assembler follows the RELECOV/PathoCore UBI httpd pattern and generates:

- `deployment/apache/00-logs.conf`;
- `deployment/apache/01-reverse-proxy.conf` from either
  `ADDONS.apache.VIRTUAL_HOSTS` or `ADDONS.apache.ROUTES`;
- `deployment/apache/02-server-status.conf` with local-only access;
- dependency health ordering, a TCP health check and configurable host port;
- a persistent production log bind and a disposable test log volume;
- read-only static/document mounts for every selected Django service.

Apache does not own another installation-settings file. Its `APACHE_*` section
lives in one selected application service's normal production/test settings.
For a standalone project the only service is selected automatically. A
multi-app project may set `ADDONS.apache.CONFIG_SERVICE` to the service whose
settings own `APACHE_LOG_PATH`, `APACHE_BIND_HOST`, `APACHE_PORT`,
`APACHE_FORWARDED_PROTO`, `APACHE_FORWARDED_PORT`, and
`APACHE_LIMIT_REQUEST_BODY`. The scaffold appends a commented section with
useful defaults when it owns that application's profile files.

For a multi-application deployment, separate DNS names are the recommended
contract because Django, React and Keycloak can each retain their native root
URL:

```json
"apache": {
  "CONFIG_SERVICE": "web",
  "VIRTUAL_HOSTS": {
    "portal.example.org": "web",
    "api.example.org": "api",
    "identity.example.org": "keycloak"
  }
}
```

Use `ROUTES` only when every target has been configured and tested under its
external path prefix. Do not put Keycloak below an arbitrary prefix unless its
hostname/path configuration intentionally matches it:

```json
"ROUTES": {
  "/api/": "api",
  "/": "web"
}
```

Every Compose mount is commented by category:

- **required configuration binds** are generated and mounted read-only;
- **required multi-app mounts** are generated from Django service persistence;
- **optional app mounts** come from `ADDONS.apache.MOUNTS` as complete Compose
  mount strings.

The generated configuration directory and log bind have an independent Apache
host permission specification. Apache has an explicit empty running-container
mount specification because it owns no writable named volume.
