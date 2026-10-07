# Documentation

This directory contains the human-facing BU-ISCIII deployment documentation. Scaffold implementation templates remain under [`../scaffold/templates/`](../scaffold/templates/).

## Start here

Use this reading order when adopting the standard for an application:

1. Read the [application installation contract](standards/application-installation-contract.md) to understand the deployment model, generated baseline, ownership boundaries, and compliance requirements.
2. Read the documentation for the application [profile](profiles/README.md) and any selected [addons](addons/README.md). These pages describe behavior that applies only to those components.
3. Review the [infrastructure requirements](standards/infrastructure-requirements.md) and, when a new host is needed, follow [Requesting a virtual machine](guides/requesting-a-virtual-machine.md).
4. Follow [Creating a project](guides/creating-a-project.md) to define the project descriptor, generate the baseline, review ownership boundaries, and run the first scaffold check.
5. Follow [Configuration](guides/configuration.md) to prepare test settings and protected production settings. Use the [project descriptor](reference/project-descriptor.md) and [configuration variable](reference/configuration-variables.md) references when exact fields or values are needed.
6. Read the [Scaffold workflow](guides/scaffold-workflow.md) before modifying generated files or adopting a newer standard revision.
7. Follow the [Deployment workflow](guides/deployment-workflow.md) to install, validate, and accept test and production deployments.
8. Before operating production, complete the [Upgrades and rollback](guides/upgrades-and-rollback.md) and [Backups and restore](guides/backups-and-restore.md) procedures.

Every deployment starts with the synchronization gate in the [Deployment workflow](guides/deployment-workflow.md): select and record the approved standards commit or version, run `scaffold.py check` against that exact revision, and continue only when every item is `current`. If anything is not current, stop, follow the [Scaffold workflow](guides/scaffold-workflow.md), commit the synchronized application files and scaffold state, and then return to the deployment workflow.

## Choose documentation by purpose

| Need | Read |
| --- | --- |
| Understand what a compliant deployment must satisfy | [Standards](standards/README.md) |
| Perform a deployment task | [Guides](guides/README.md) |
| Look up an exact file, descriptor field, variable, or command | [Reference](reference/README.md) |
| Understand framework-specific build and runtime behavior | [Profiles](profiles/README.md) |
| Understand optional supporting services | [Addons and supporting services](addons/README.md) |

Standards are normative and answer what must be true. Guides explain how to perform a task. Reference pages describe the exact current interface. Profile and addon requirements apply only when the corresponding component is selected.

## Common paths

### Creating a new deployment

[Installation contract](standards/application-installation-contract.md) → [selected profiles](profiles/README.md) and [addons](addons/README.md) → [infrastructure requirements](standards/infrastructure-requirements.md) → [creating a project](guides/creating-a-project.md) → [configuration](guides/configuration.md) → [deployment workflow](guides/deployment-workflow.md)

### Deploying or upgrading an existing application

[Scaffold workflow](guides/scaffold-workflow.md) → commit the synchronized baseline → [configuration](guides/configuration.md) → [deployment workflow](guides/deployment-workflow.md) → [upgrades and rollback](guides/upgrades-and-rollback.md)

### Maintaining this standards repository

Read [`AGENTS.md`](../AGENTS.md), then use the implementation under `lib/`, `scaffold/templates/`, `scripts/`, and `tests/` as the source of truth. Use [Reference](reference/README.md) to verify documented interfaces and [Standards](standards/README.md) to verify normative requirements.

## Documentation map

- [Standards](standards/README.md) — application, infrastructure, security, and compliance requirements.
- [Guides](guides/README.md) — project creation, synchronization, configuration, deployment, upgrades, and recovery procedures.
- [Reference](reference/README.md) — generated structure, descriptor schema, configuration variables, and script interfaces.
- [Profiles](profiles/README.md) — Django, Next.js, and React/Vite behavior.
- [Addons and supporting services](addons/README.md) — Apache, Keycloak, MySQL support, Nextstrain, and Samba.
