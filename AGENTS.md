# BU-ISCIII Deployment Standards

This repository defines reusable deployment standards, scaffold templates and shared deployment utilities for BU-ISCIII applications.

Changes should remain generic enough to be useful across applications. This repository must not accumulate application-specific deployment logic that belongs in an individual application repository.

## General principles

- Prefer reusable solutions over application-specific implementations.
- Keep common behavior independent of frameworks and applications.
- Put framework-specific behavior in the corresponding profile.
- Put optional infrastructure or integration behavior in the corresponding addon.
- Do not add functions, paths, service names, settings or assumptions that are only useful for one application.
- When an application needs special behavior, provide a clear extension point rather than adding the application logic to the standard.
- Keep the implementation understandable to developers who did not originally write it.

Before changing an existing abstraction, inspect how it is used by the scaffold, profiles, addons and tests.

## Source of truth

For implemented deployment behavior, use the code, templates and tests as the source of truth.

Relevant areas include:

- `scripts/scaffold.py`: scaffold compiler and synchronization logic.
- `lib/container/`: reusable container and deployment functions.
- `scaffold/templates/common/`: framework-independent generated files.
- `scaffold/templates/profiles/`: framework-specific behavior.
- `scaffold/templates/addons/`: optional deployment components.
- `tests/`: expected contracts and boundaries.
- `docs/standards/`: normative requirements.
- `docs/guides/`: task-oriented documentation.
- `docs/reference/`: detailed implementation reference.

Do not change code simply to make it match outdated documentation. Identify the difference first and decide whether the code or documentation should change.

## Architecture boundaries

Preserve the separation between common behavior, profiles, addons and application-specific behavior.

### Common code

Common code must work without knowing which application is being deployed.

Good examples include:

- container-engine selection;
- Compose invocation;
- configuration validation;
- generic permission helpers;
- common diagnostics;
- scaffold rendering and synchronization.

Common code must not contain Django-, React-, Next.js-, Apache-, Keycloak- or application-specific assumptions unless those are necessary to dispatch to an explicit extension point.

### Profiles

Framework-specific behavior belongs under:

`scaffold/templates/profiles/<profile>/`

Examples include:

- Django migrations and settings;
- React/Vite build behavior;
- Next.js runtime behavior;
- profile-specific Dockerfiles;
- profile-specific health checks;
- profile-specific bootstrap logic.

Do not move profile behavior into `scripts/scaffold.py` or common shell libraries merely to reduce the number of files.

### Addons

Optional supporting components belong under:

`scaffold/templates/addons/<addon>/`

Examples include Apache and Keycloak.

An addon should remain independent from any one application whenever possible.

### Application-specific behavior

Application-specific changes belong in the application repository.

Use the existing application-owned blocks and extension hooks when generated files need customization.

Do not add a function to this repository only because one application needs it, unless the function represents reusable deployment behavior.

## Keep the scaffold compiler generic

`scripts/scaffold.py` should coordinate and assemble deployment components, not implement framework runtime behavior.

Prefer:

- profile templates for profile behavior;
- addon templates for addon behavior;
- shared libraries for reusable runtime operations;
- small compiler functions that assemble these pieces.

Avoid embedding generated Compose YAML, framework commands, runtime paths, framework defaults or application-specific values directly in `scripts/scaffold.py` when they can live in their owning template.

## Code style

Prefer simple and explicit code.

Optimize primarily for:

1. correctness;
2. readability;
3. reuse;
4. maintainability;
5. then compactness.

Reducing duplicated code is desirable, but not when the abstraction becomes harder to understand than the duplicated code.

Avoid large functions that try to handle unrelated cases through many flags or conditions.

Prefer small functions with one clear responsibility.

Reuse an existing helper when its purpose matches the new behavior. Do not force unrelated behavior into a helper only to avoid adding a few lines.

## Python

For Python code:

- use type annotations for function parameters and return values;
- add a short docstring to public or non-obvious functions;
- prefer standard-library functionality unless an external dependency provides a clear benefit;
- use `pathlib.Path` for filesystem paths;
- prefer descriptive names over short names;
- keep validation close to the input it validates;
- raise clear errors that explain what the user needs to correct;
- use dataclasses or small structured objects when they make related data easier to understand;
- avoid unnecessary classes when functions and simple data structures are enough.

Example:

```python
def load_project(path: Path) -> dict[str, Any]:
    """Load and validate the project descriptor."""
```

Do not add comments that merely repeat the code.

Use comments to explain:

- why a non-obvious decision exists;
- ownership boundaries;
- compatibility requirements;
- security-sensitive behavior;
- behavior that must remain synchronized with another component.

## Shell

Shell scripts are part of the public deployment interface and should remain readable.

- Use descriptive function and variable names.
- Keep functions focused on one operation.
- Prefer shared helpers in `lib/container/` for reusable behavior.
- Fail early with a clear error message.
- Quote variables unless shell splitting is explicitly required.
- Avoid hidden side effects.
- Keep lifecycle steps visible in the main installer.
- Comment important lifecycle stages and non-obvious engine-specific behavior.
- Do not hide the whole deployment workflow behind generic helper functions.

A reader should be able to open `container_install.sh` and understand the main deployment sequence without tracing dozens of helper calls.

## Docker and Podman

The standard supports Docker and Podman.

Do not assume their behavior is identical.

- Do not require rootless Docker unless the implementation explicitly changes to require it.
- Rootless Podman and user namespaces must be considered where they affect permissions and ownership.
- Keep engine-independent behavior in common helpers.
- Isolate engine-specific handling where necessary.
- Do not introduce Docker-only or Podman-only behavior into common workflows without an explicit compatibility decision.

## Permissions and security

Avoid broad permission changes such as recursive `chmod 777`.

Permission logic should:

- operate only on declared paths;
- distinguish host paths from paths inside containers;
- use the minimum required ownership and mode;
- account for rootless Podman user namespaces where relevant;
- remain compatible with the supported Docker path.

Do not disable SELinux as a solution to filesystem access problems.

Keep production secrets and sensitive configuration out of committed files and container image layers according to the existing deployment model.

Security controls should be understandable and connected to a concrete risk; avoid adding security options simply because they are generally considered best practice.

## Generated files and ownership

Respect the generated-file ownership model.

Some files are fully managed by the standard, some contain explicit application-owned blocks, and some are application-owned.

Do not make locally editable copies of shared libraries.

Reusable common libraries under `deployment/lib/` are generated from `lib/` and should remain synchronized with the canonical implementation.

When adding customization, prefer an existing application-owned block or explicit callback. Add a new extension point only when the behavior is likely to be reusable.

## Naming

Names should describe their actual role.

Avoid generic names such as:

- `app`;
- `app_db`;
- `service1`;
- `helper`;
- `process_data`;

when a meaningful domain-independent name is available.

Service names are deployment identities and should remain stable between standalone and orchestrated deployments.

Prefer names that work naturally as Compose service/DNS names.

## Comments and documentation

Code should be understandable without excessive comments.

Comments should explain **why**, not restate **what** the next line does.

For complex or security-sensitive behavior, briefly explain:

- the problem being solved;
- any Docker/Podman difference;
- any ownership or permission assumption;
- why the behavior belongs in the common layer, profile or addon.

Keep documentation concise and in plain English.

For documentation-specific work, use the `deployment-standards-documentation` skill.

## Tests

Changes to deployment behavior should include or update tests.

Tests should verify contracts and boundaries, not only successful execution.

In particular, preserve tests that ensure:

- common code remains framework-independent;
- profile behavior stays in profile templates;
- addon behavior stays in addon templates;
- generated files remain deterministic;
- application-owned sections are preserved;
- Docker and Podman interfaces remain compatible where promised;
- invalid configuration fails clearly.

Prefer small focused tests over large duplicated test scenarios.

Do not weaken an existing architectural test simply because a new implementation violates the boundary it protects. Reconsider the implementation first.

## Making changes

For a change that introduces new behavior:

1. identify whether it is common, profile-specific, addon-specific or application-specific;
2. place it in the corresponding layer;
3. reuse existing helpers where appropriate;
4. keep the implementation as small and clear as practical;
5. add or update tests;
6. update documentation when the public deployment contract changes.

Avoid unrelated refactoring in the same change.

## Before finishing

Check that:

- the code is reusable and not tied to one application;
- common code contains no unnecessary framework-specific logic;
- functions are small and clearly named;
- Python functions have useful type annotations;
- non-obvious functions have concise docstrings;
- important decisions are commented;
- duplicated logic has been reused where doing so improves clarity;
- Docker and Podman behavior has been considered separately where necessary;
- tests cover new behavior;
- generated artifacts still follow repository ownership rules;
- documentation matches the resulting implementation.

Run the relevant test suite and syntax checks for the files changed.
