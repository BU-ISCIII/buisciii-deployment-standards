# Addons and supporting services

An addon adds optional supporting infrastructure or deployment functionality to one or more application services.

- [Apache](apache.md) — reverse proxy, host-facing exposure, and Django static/document serving.
- [Keycloak](keycloak.md) — shared identity/OIDC service and persistent identity database.
- [Mailpit](mailpit.md) — disposable, test-only SMTP catcher and local inbox.
- [MySQL support](mysql.md) — Django test database and optional Compose-managed production database. It is selected through Django's `DATABASE` field, not `ADDONS.mysql`.
- [Nextstrain](nextstrain.md) — Auspice visualization service backed by reviewed dataset storage.
- [Samba](samba.md) — internal, disposable, test-only filesystem sharing.

Selectable addon implementation sources are under [`../../scaffold/templates/addons/`](../../scaffold/templates/addons/). MySQL remains Django-owned implementation support under `scaffold/templates/profiles/django/`.
