# BU-ISCIII Deployment Standards

This repository provides reusable deployment standards, scaffold generation, and shared container libraries for BU-ISCIII application teams and deployment operators. It generates synchronized Docker Compose deployments while keeping application frameworks, optional infrastructure, and application-owned behavior separate.

## What the repository provides

- normative deployment, infrastructure, and security standards;
- a descriptor-driven scaffold with `init`, `check`, and `sync` workflows;
- generated production and test Compose models;
- shared host/container deployment libraries;
- framework-specific application profiles and optional supporting components; and
- Docker, Podman, and rootless Podman support. Rootless Docker is not required.

## Supported deployment model

Each application service selects one profile. A project may contain one service or several services assembled by an orchestrator. Optional addons add shared infrastructure without becoming application profiles. Generated files retain declared standard-managed and application-owned boundaries so central improvements can be checked and synchronized safely.

### Application profiles

- [Django](docs/profiles/django.md)
- [Next.js](docs/profiles/nextjs.md)
- [React/Vite](docs/profiles/react-vite.md)

### Addons and supporting services

- [Apache](docs/addons/apache.md) — optional reverse proxy and application exposure.
- [Keycloak](docs/addons/keycloak.md) — optional identity and OIDC infrastructure.
- [MySQL support](docs/addons/mysql.md) — Django-owned test database and optional production Compose database; not selected through `ADDONS.mysql`.
- [Nextstrain](docs/addons/nextstrain.md) — optional Auspice visualization service.
- [Samba](docs/addons/samba.md) — disposable, test-only SMB storage.

## Quick start

Copy and edit a current descriptor example, then generate and check the application baseline:

```bash
cp scaffold/project.json.example /tmp/project.json
python3 scripts/scaffold.py init /path/to/application --config /tmp/project.json
python3 scripts/scaffold.py check /path/to/application
```

See [Creating a project](docs/guides/creating-a-project.md) for the complete workflow.

## Documentation

See the [documentation index](docs/README.md). Useful starting points include the [application installation contract](docs/standards/application-installation-contract.md), [deployment workflow](docs/guides/deployment-workflow.md), [project descriptor reference](docs/reference/project-descriptor.md), and [exceptions and compliance standard](docs/standards/exceptions-and-compliance.md).

## Repository structure

```text
docs/       Human-facing standards, guides, reference, profiles, and addons
lib/        Shared application-neutral deployment libraries
scaffold/   Descriptor examples and generated-file implementation templates
scripts/    Scaffold initialization and synchronization tooling
tests/      Contract and generation tests
```

`scaffold/templates/` contains implementation sources rendered into application repositories; it is not documentation storage.

## Development and contributing

Read [AGENTS.md](AGENTS.md) before changing the repository. Keep common behavior application-neutral, put framework behavior in profile templates, put optional infrastructure behavior in addon templates, and preserve generated-file ownership contracts. Run relevant tests and `git diff --check` before submitting changes.

See [CHANGELOG.md](CHANGELOG.md) for notable changes.
