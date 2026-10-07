---
name: deployment-standards-documentation
description: Document and review the BU-ISCIII deployment standard. Use when writing or modifying standards, guides, reference pages, profiles, addons, templates, or deployment documentation in this repository.
---

# BU-ISCIII deployment documentation

Use this skill for documentation work in this repository.

The documentation must describe the deployment system that is actually implemented. Do not design a different deployment system while documenting it.

## 1. Source of truth

Before documenting a behavior, inspect the relevant implementation.

Use, as applicable:

- `lib/container/`
- `scaffold/templates/common/`
- `scaffold/templates/profiles/`
- `scaffold/templates/addons/`
- `scripts/scaffold.py`
- `tests/`
- `scaffold/project*.json.example`
- existing profile and addon documentation

Treat scripts, templates and tests as the primary evidence for implemented behavior.

Existing documentation may be outdated. Do not copy a statement from an existing document without checking that it still matches the code.

If documentation and implementation disagree:

1. follow the implementation when describing current behavior;
2. do not invent a requirement to reconcile them;
3. report the discrepancy at the end of the task.

## 2. Do not invent requirements

Every normative requirement must be supported by the repository implementation or by an explicit existing design decision.

In particular:

- Docker and Podman are supported container engines.
- Do not state that Docker must run rootless unless the implementation is changed to require this.
- Rootless Podman and its user-namespace behavior must be documented where relevant because the deployment helpers explicitly support it.
- Do not generalize Podman-specific behavior to Docker.
- Do not claim complete Docker/Podman equivalence when behavior is engine-specific.
- Do not introduce new ports, paths, permission rules, container options, SELinux rules, backup policies, or security controls only because they are considered general best practice.

External best practices may be mentioned as recommendations only when clearly separated from the BU-ISCIII contract.

## 3. Documentation layers

Keep the purpose of each documentation area clear.

### `docs/standards/`

Defines what a compliant BU-ISCIII deployment MUST, SHOULD or MAY do.

Standards answer:

> What must be true?

They should not contain long tutorials or exhaustive command references.

### `docs/guides/`

Procedural documentation.

Guides answer:

> How do I do this?

### `docs/reference/`

Exact behavior of scripts, configuration, generated files and interfaces.

Reference pages answer:

> What is this and exactly how does it behave?

### `docs/profiles/`

Framework-specific behavior such as Django, Next.js or React/Vite.

### `docs/addons/`

Optional supporting deployment components such as Apache or Keycloak.

Do not duplicate large explanations between these layers. Use links.

## 4. Writing style

Keep documentation as short as possible while still being understandable by someone who has little or no container experience.

Use:

- plain English;
- short sentences;
- short paragraphs;
- concrete names;
- small tables where they simplify comparison;
- one short example when a concept is difficult to understand.

Avoid:

- unnecessarily formal language;
- long definitions;
- unexplained container terminology;
- repeating the same concept in several sections;
- large command listings when a reference page is more appropriate;
- generic security prose that is not connected to the implementation.

Prefer:

> A bind mount makes a host file or directory available inside a container.

over:

> Bind mounts provide a mechanism through which host filesystem resources can be projected into the container namespace.

## 5. Explain container concepts briefly

Assume that the reader understands Linux administration but may not have worked with containers.

When a container-specific concept first matters, explain it in one or two sentences.

Typical concepts include:

- image;
- container;
- Compose service;
- bind mount;
- named volume;
- container network;
- container UID/GID;
- rootless Podman;
- user namespace;
- build context;
- build-time versus runtime configuration;
- health/readiness check.

Do not turn the standard into a container tutorial.

Link to upstream documentation for deeper explanations.

## 6. External references

Use authoritative upstream documentation when it helps explain a concept.

Prefer:

- Docker documentation for Docker and Compose;
- Podman documentation for Podman and rootless/user namespaces;
- Red Hat documentation for SELinux on RHEL-compatible systems;
- Django documentation for Django;
- Vite documentation for Vite;
- Next.js documentation for Next.js;
- Keycloak documentation for Keycloak;
- Apache HTTP Server documentation for Apache.

External references explain the technology. They do not define the BU-ISCIII deployment contract.

Keep references close to the relevant concept or in a short `Further reading` section.

Do not add many links when one authoritative reference is sufficient.

## 7. Normative language

Use:

- **MUST** for a requirement necessary to comply with the standard;
- **SHOULD** for the expected approach when a documented exception may be valid;
- **MAY** for optional behavior.

Use normative words sparingly.

Before writing `MUST`, verify that the repository implementation supports or enforces the requirement.

A security recommendation from an external project is not automatically a BU-ISCIII `MUST`.

## 8. Security and functionality rationale

When a design choice is important, briefly explain why it exists.

Prefer one sentence.

Example:

> Production Django settings are rendered outside the image so production secrets are not stored in an image layer.

Avoid generic statements such as:

> This improves security.

Explain the concrete effect instead.

Cover both functionality and security where relevant.

Important areas include:

- production configuration;
- build-time versus runtime settings;
- permissions;
- Docker versus rootless Podman;
- user namespaces;
- SELinux;
- bind mounts;
- network exposure;
- persistent data;
- test versus production data;
- image contents;
- application bootstrap;
- backups and restore.

Again, document only controls that the repository actually implements or explicitly requires.

## 9. Docker and Podman

Always check engine-specific code before describing behavior.

The deployment standard supports Docker and Podman.

Do not write:

> Containers run rootless.

unless the statement applies to the specific engine and deployment being described.

For Podman, explain rootless behavior and user namespaces where the permission code depends on them.

For Docker, document the behavior implemented by the Docker branch of the shared helpers.

When behavior differs, say so explicitly.

Example:

> The same permission specification is used for both engines. With rootless Podman, container UIDs may need to be translated through the user namespace before changing ownership on the host.

## 10. SELinux

Do not assume SELinux is disabled.

When SELinux matters:

- explain briefly what problem it can cause;
- distinguish normal Unix permissions from SELinux access control;
- describe only the labeling or mount behavior implemented by the repository;
- link to authoritative SELinux documentation for deeper explanation.

Never recommend disabling SELinux as the normal solution.

If the repository does not yet automate a required SELinux step, document that limitation instead of pretending it does.

## 11. Configuration and secrets

Clearly distinguish:

- project/scaffold configuration;
- build configuration;
- runtime configuration;
- sensitive values/secrets.

Check the actual templates before classifying a value.

Do not show real secrets in examples.

Use `CHANGE_ME`, `<value>`, or an obviously fake example where appropriate.

When explaining Django production settings, make clear whether settings are generated during the build or at runtime according to the actual profile implementation.

## 12. Examples

Use examples only when they reduce ambiguity.

Examples must:

- match the current CLI;
- use existing file names;
- use existing engine options;
- avoid real credentials;
- avoid creating behavior unsupported by the scripts.

Prefer one representative example rather than several variations.

## 13. Mermaid diagrams

Keep Mermaid diagrams when they make the architecture or lifecycle easier to understand.

Prefer small diagrams.

Do not duplicate information already obvious from the text.

Existing useful diagrams should be preserved unless they no longer match the implementation.

## 14. Before finishing a documentation change

Check:

1. Does every behavioral statement match the current code?
2. Does every `MUST` correspond to a real contract requirement?
3. Did I accidentally make rootless execution mandatory for Docker?
4. Did I distinguish Docker behavior from rootless Podman where needed?
5. Did I explain unfamiliar container concepts briefly?
6. Can any paragraph be made shorter without losing meaning?
7. Is detailed implementation material better placed in `docs/reference/`?
8. Is procedural material better placed in `docs/guides/`?
9. Are external links authoritative and useful?
10. Do examples use the current commands and file names?
11. Are existing useful diagrams still correct?
12. Did I introduce any requirement that exists only in external documentation?

At the end of the task, report:

- files changed;
- important content moved or removed;
- implementation/documentation discrepancies found;
- any point that needs a human decision.

Do not modify deployment behavior unless the task explicitly requests code changes.
