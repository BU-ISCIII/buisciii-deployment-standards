# Guides

Guides are procedural: they explain how to perform deployment work. Normative requirements belong in [standards](../standards/README.md), while exact interfaces belong in [reference](../reference/README.md).

## Getting started

- [Requesting a virtual machine](requesting-a-virtual-machine.md) — collect development host, network, storage, and access requirements.
- [Preparing production infrastructure](preparing-production-infrastructure.md) — turn production infrastructure requirements into a reviewed readiness record.
- [Creating a project](creating-a-project.md) — create a descriptor and initialize the scaffold.
- [Scaffold workflow](scaffold-workflow.md) — check, synchronize, and resolve generated-file ownership states.

## Preparing a deployment

- [Configuration](configuration.md) — prepare settings, secrets, and cross-service values.
- [Ignore files](ignore-files.md) — understand generated Git and build exclusions.
- [Docker Compose](docker-compose.md) — understand the generated topology, networks, ports, and storage.
- [Container installer customization](container-install-customization.md) — use supported application-owned hooks.

## Operating a deployment

- [Deployment workflow](deployment-workflow.md) — install and validate a deployment.
- [Generated documentation files](documentation-files.md) — maintain application README and operator runbook content.
- [Upgrades and rollback](upgrades-and-rollback.md) — prepare upgrades and recovery decisions.
- [Backups and restore](backups-and-restore.md) — protect and recover persistent state.
