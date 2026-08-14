# Changelog

## Unreleased

- Document and inventory the automatically staged Keycloak realm bind whenever
  the add-on is selected, including optional hardened-host pre-creation steps.
- Document a complete optional second-DNS Apache virtual host and its matching
  per-vhost settings set, with the same forwarded headers, limits, timeouts,
  and per-host logging as the default.
- Stage repository-owned Keycloak realm JSON into the deployment bind tree and
  assign the staged files to Keycloak instead of modifying repository sources.
- Print a final Compose service summary after successful container installation
  so operators can see the running services and copy their published host ports.
- Reduced configuration to one production/test settings pair per application:
  internal build/bootstrap paths are no longer descriptor inputs, and Apache
  or Keycloak reuse namespaced sections in a selected application settings
  file instead of creating add-on-specific files.
- Made service settings the single source for repository/install/host paths,
  application ports and UID/GID. The generated environment now supplies these
  values to Docker builds, Compose, Apache routing and lifecycle checks;
  `project.json` retains only the Django `PROJECT_MODULE` structural value.
- Consolidated `container_install.sh`, README, LEAME, the Compose document,
  `.dockerignore`, `.gitignore` and smoke dispatch into common templates used by
  standalone and multi-service deployments.
- Restricted Django and React/Vite profiles to framework-owned Dockerfiles,
  inner installers, entrypoints and configuration while selecting profiles
  independently per normalized service.
- Added add-on catalog documentation for Apache and Keycloak without exposing
  separate operator-facing Compose overlays.
- Added service-oriented project descriptors: each service independently
  selects Django or React/Vite, while Apache and Keycloak are assembled as real
  add-on services into one production and one test Compose document.
- Replaced separate standalone/orchestrator examples with one canonical
  `project.json` schema using one or many `SERVICES` entries; retained the old
  top-level `PROFILE` shape only for synchronization of initialized projects.
- Expanded Apache to the RELECOV/PathoCore operational pattern: UBI httpd,
  dependency health ordering, separate proxy/log/status binds, persistent logs,
  generated read-only Django static/document mounts with classified mount
  comments, and per-service DNS virtual hosts for mixed applications.
- Expanded Keycloak to the PathoCore pattern with a health-checked MySQL
  service, persistent database volume, strict proxy/hostname settings,
  reproducible realm-import bind, and separate Keycloak/database permissions.
- Added a single shared Django settings renderer for `install.sh` and
  `container_install.sh`.
- Standardized explicit test-only image settings rendering.
- Added ephemeral production installation-config build secrets and mandatory
  `.dockerignore` protection so operator credentials are not retained in image
  layers.

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
- Split the canonical CLI into separate consistent interfaces for `install.sh`
  and `container_install.sh`; scripts no longer need to recognize options owned
  only by the other script type.
- Add the versioned shared container installer library, library tests, and
  `check-lib`/`sync-lib` commands; refactor RELECOV Platform and iSkyLIMS to
  source identical vendored copies while retaining application-specific logic.
- Keep this release intentionally manual while it is reviewed against
  PathoCore and RELECOV.
