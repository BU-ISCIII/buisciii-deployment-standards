# Documentation

This directory contains the human-facing BU-ISCIII deployment documentation. Scaffold implementation templates remain under [`../scaffold/templates/`](../scaffold/templates/).

## Getting started

- [Requesting a virtual machine](guides/requesting-a-virtual-machine.md) — collect infrastructure requirements and request inputs.
- [Creating a project](guides/creating-a-project.md) — prepare a descriptor and initialize a deployment baseline.
- [Scaffold workflow](guides/scaffold-workflow.md) — check, synchronize, and resolve generated-file changes.
- [Configuration](guides/configuration.md) — prepare test and protected production settings.
- [Deployment workflow](guides/deployment-workflow.md) — execute installation and acceptance in order.
- [Upgrades and rollback](guides/upgrades-and-rollback.md) — synchronize and deploy reviewed changes safely.
- [Backups and restore](guides/backups-and-restore.md) — inventory persistent data and recovery procedures.

## Standards

Standards are normative requirements describing what a compliant deployment must satisfy. See the [standards index](standards/README.md) for the application installation contract, infrastructure requirements, security requirements, and exceptions/compliance process.

## Guides

Guides are task-oriented instructions for common deployment work. See the [guides index](guides/README.md).

## Reference

Reference pages describe exact current interfaces and behavior, including the [generated project structure](reference/generated-project-structure.md), [project descriptor](reference/project-descriptor.md), [configuration variables](reference/configuration-variables.md), and [generated scripts](reference/scripts/README.md).

## Profiles

A profile defines how an application service is built, started, and deployed. Current profiles are [Django](profiles/django.md), [Next.js](profiles/nextjs.md), and [React/Vite](profiles/react-vite.md). See the [profiles index](profiles/README.md).

## Addons and supporting services

An addon adds optional supporting infrastructure or deployment functionality to application services. The catalog documents [Apache](addons/apache.md), [Keycloak](addons/keycloak.md), [MySQL support](addons/mysql.md), [Nextstrain](addons/nextstrain.md), and [Samba](addons/samba.md). MySQL is documented here as supporting infrastructure but is generated through Django's `DATABASE` option rather than `ADDONS.mysql`. See the [addons index](addons/README.md).

## Operational templates

[`templates/`](templates/README.md) contains human-facing checklists and configuration review forms. It is distinct from the scaffold implementation under `scaffold/templates/`.

## Audits

[`audits/`](audits/) contains dated or focused assessments. Audits record findings; they do not replace the current standards, guides, or reference.
