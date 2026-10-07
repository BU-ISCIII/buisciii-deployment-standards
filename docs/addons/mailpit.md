# Mailpit addon

Mailpit captures outgoing email in local/test stacks. It has no production service; production applications and Keycloak must use the SMTP endpoint selected by the deployment operator.

Select it in the project descriptor:

```json
"mailpit": {
  "CONFIG_SERVICE": "example-app",
  "MODES": ["test"]
}
```

The addon generates `<APP_SLUG>-mailpit` using `axllent/mailpit:v1.27`, with the stable network alias `mailpit`. Configure application or Keycloak test SMTP settings to use `mailpit:1025`; selecting the addon does not change those settings automatically. Disable SMTP authentication and TLS for this disposable catcher.

`MAILPIT_SMTP_PORT` and `MAILPIT_WEB_PORT` default to `1025` and `8025`. Both host ports bind to `127.0.0.1`. Open `http://127.0.0.1:8025` to inspect captured messages. The healthcheck probes `/livez`; the addon declares no persistent volume, so captured mail is disposable.

Settings are generated under `conf/mailpit/`. The production settings file contains only comments. See the [project descriptor](../reference/project-descriptor.md) and [configuration variables](../reference/configuration-variables.md).
