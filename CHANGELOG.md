# Changelog

## 0.1.0 - 2026-08-04

- Add the initial technology-neutral application installation contract.
- Require every installation script to expose the same canonical command-line
  options, with explicit failure for capabilities not yet implemented.
- Add Django, React/Vite, Keycloak, and MySQL profiles.
- Add detailed installation audit and configuration matrix templates.
- Add a renderable Django deployment scaffold based on the RELECOV layout,
  including README/LEAME, canonical installers, Docker assets, settings
  documentation, and smoke tests.
- Add safe checksum-based synchronization with conflict candidates instead of
  overwriting application changes.
- Align the generated container entrypoint with the RELECOV Platform/iSkyLIMS
  runtime pattern: bounded staging checks, safe permissions, optional Django
  cron jobs through supercronic, dynamic workers, and complete Gunicorn tuning.
- Make stage/bootstrap separation, ordered migration hooks, fixture controls,
  Compose overrides, and orchestrator configuration mapping part of the
  canonical installer contract and scaffold.
- Rewrite the application installation contract as a template-linked practical
  guide with commands and Mermaid diagrams for structure, lifecycle, script
  ownership, configuration, rollback, and synchronization.
- Keep this release intentionally manual while it is reviewed against
  PathoCore and RELECOV.
