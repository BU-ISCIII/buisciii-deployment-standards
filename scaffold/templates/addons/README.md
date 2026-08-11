# Compose add-on catalog

Add-ons contribute marked blocks to the one generated Compose file and append
their services to `permission_services` when they own writable mounts. They do
not select or replace an application's framework profile.

The generic assembler discovers Apache, Keycloak, Nextstrain, and Samba from their catalog
directories. Each catalog entry owns its Compose, settings, installer,
permission, and documentation fragments.

`ADDONS` is an object keyed by add-on name. An empty object disables all
add-ons:

```json
"ADDONS": {}
```

A standalone application can select both current add-ons as follows:

```json
"ADDONS": {
  "apache": {
    "CONFIG_SERVICE": "app",
    "MOUNTS": []
  },
  "keycloak": {
    "CONFIG_SERVICE": "app"
  }
}
```

`CONFIG_SERVICE` identifies the application used for add-on relationships and
derived defaults. Add-on values remain in `conf/<addon>/` and are mapped with
the same repeatable `--install_conf_map` option as applications. `MOUNTS` is optional and contains complete
Compose mount strings contributed to an add-on that provides an
`application-mount` fragment; Apache currently supports it. For example:

```json
"MOUNTS": [
  "/srv/public-downloads:/var/www/downloads:ro,Z"
]
```

Do not add separate `INSTALL_CONF`, `TEST_INSTALL_CONF`, `ROUTES`, or
`VIRTUAL_HOSTS` descriptor keys. Add-on settings follow the catalog convention, and
Apache routes are maintained directly in `conf/apache/01-reverse-proxy.conf`.

See `scaffold/project.addons.json.example` for a complete valid descriptor.
