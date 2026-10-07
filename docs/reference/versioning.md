# Deployment component versioning

## Purpose

This page defines how maintainers classify and coordinate changes to the independently versioned deployment components in this repository. These versions describe compatibility surfaces inside generated deployment tooling; they are not application versions, container image tags, dependency versions, or a single repository release number.

The repository uses `MAJOR.MINOR.PATCH` markers and applies the compatibility categories from [Semantic Versioning 2.0.0](https://semver.org/) to each component's documented contract. The component scopes below define what counts as that component's public contract.

## Current version inventory

| Component | Version constant and location | Current value | Scope |
| --- | --- | ---: | --- |
| Generated container installer | `APP_VERSION` in `scaffold/templates/common/container_install.sh.tmpl` | `0.1.0` | Outer deployment CLI, configuration resolution, lifecycle, profile/addon dispatch, permissions, bootstrap, data loading, and smoke-test orchestration |
| Generated Django installer | `APP_VERSION` in `scaffold/templates/profiles/django/install.sh.tmpl` | `0.2.0` | Django direct install, image staging, runtime bootstrap, migrations, fixtures, hooks, and static collection |
| Common container library | `BU_ISCIII_CONTAINER_LIB_VERSION` in `lib/container/common.sh` | `0.1.0` | Shared Docker/Podman, Compose, configuration, permission, diagnostic, and deployment-validation helpers |
| Django container library | `BU_ISCIII_DJANGO_CONTAINER_LIB_VERSION` in `lib/container/django.sh` | `0.2.0` | Shared Django settings rendering and Django-specific host/container configuration helpers |
| Scaffold state format marker | `standard_version` written by `scripts/scaffold.py` | `0.1.0` | `.bu-isciii-deployment/state.json` format and interpretation |

No other generated script, profile, addon, or scaffold command currently exposes an explicit deployment-component version. Base-image tags, `PYTHON_VERSION`, the pinned Supercronic version, and application `GIT_REVISION` values version dependencies or deployed application input, not the deployment contracts listed above.

## Independent scopes

The versions move independently because their compatibility surfaces differ. A backward-compatible fix in a generic Compose helper can change only the common-library version. A Django settings-rendering change can affect only the Django library. A new outer-installer option affects the container installer, while a migration-order change affects the Django installer. One repository change may affect several scopes, but unrelated components do not receive synchronized version bumps.

The repository currently has no monolithic release-version constant and no established Git-tag convention. Component versions and the scaffold state marker are therefore not substitutes for recording the approved repository commit used to generate or synchronize an application.

## Version classification

Apply the following classification independently to every affected component:

| Change | Meaning |
| --- | --- |
| `PATCH` | Backward-compatible correction that preserves the documented inputs, outputs, and contract, such as a helper bug fix or improved diagnostics |
| `MINOR` | Backward-compatible capability or documented behavior that existing generated applications can continue using unchanged, such as a new optional CLI option or helper |
| `MAJOR` | Backward-incompatible contract change requiring application, operator, state, configuration, hook, or persistent-data migration |

The current versions are below `1.0.0`, but maintainers should still use these compatibility categories consistently. A documentation-only correction normally requires no component bump. If documentation reveals an implementation change that was not versioned, classify and version the implementation change rather than bumping solely because the prose changed.

## Compatibility dimensions

Assess every behavior change against the dimensions it can affect:

| Dimension | Question |
| --- | --- |
| CLI | Do existing documented commands, options, arguments, exit codes, and action semantics still work? |
| Configuration | Do existing descriptors and installation settings remain valid, and are new fields optional or safely synchronized? |
| Generated files | Can initialized applications run `check` and `sync` without unsupported replacement or manual reconstruction? |
| Application hooks | Do existing application-owned blocks, functions, arguments, and return expectations remain valid? |
| Library API | Do generated scripts still call available helpers with compatible names, arguments, output, and failure behavior? |
| Persistent data | Are database schemas, named volumes, bind paths, ownership, file formats, and backup/restore expectations compatible? |
| Profiles and addons | Does an existing descriptor retain compatible build, runtime, readiness, bootstrap, networking, and persistence behavior? |
| Scaffold state | Can the current scaffold read and interpret existing `.bu-isciii-deployment/state.json` files, or is a migration required? |

Operational impact can make an otherwise small code edit a major contract change. For example, changing a persistent volume destination or removing a required configuration name is not merely a template refactor.

## Component bump rules

### Generated container installer

Bump the generated container installer `APP_VERSION` when its public CLI or deployment lifecycle changes. Relevant changes include options and exit behavior, action semantics, configuration resolution, significant lifecycle ordering, readiness/bootstrap dispatch, permission phases, data-loading behavior, and application-hook contracts. Do not bump it for an unrelated library or documentation change when the generated installer contract is unchanged.

### Common container library

Bump `BU_ISCIII_CONTAINER_LIB_VERSION` when the API or behavior of canonical shared helpers changes. This includes engine selection, Compose invocation, configuration and environment rendering, permission helpers, diagnostics, runtime configuration staging, smoke-test helpers, and deployment-configuration validation.

### Django container library

Bump `BU_ISCIII_DJANGO_CONTAINER_LIB_VERSION` when reusable Django-specific helper behavior or API changes, including settings rendering, settings bind preparation, generated secret handling, or Django-specific permission/configuration helpers.

### Generated Django installer

Bump the Django installer `APP_VERSION` when Django stage, bootstrap, or direct-install interfaces or semantics change. This includes its CLI, stage contract, required artifacts, bootstrap ordering, database waiting and checks, migration hooks, fixture/table behavior, settings rendering, static collection, and application callback contracts.

### Scaffold state format

Change the scaffold `standard_version` when the persisted state format or interpretation changes. A backward-compatible optional field is a minor candidate; a compatible correction is a patch candidate; removing or reinterpreting required state without an automatic compatibility path is a major candidate. The current implementation writes this marker but does not validate it or dispatch migrations from it, so any state-format change must include explicit compatibility handling or migration instructions.

## Compatibility decision

Use this decision for each affected component:

```text
Does component behavior change?
  no  -> no component version bump
  yes -> does a documented or public contract change?
           no  -> PATCH candidate
           yes -> can existing consumers continue unchanged?
                    yes -> MINOR candidate
                    no  -> MAJOR candidate
```

Apply the decision independently. A single repository change can be a patch for one component, a minor change for another, or affect only one component.

## Coordinated deployment compatibility changes

A **coordinated deployment compatibility change** is one change set containing the artifacts needed to introduce a deployment-contract change safely. Its purpose is atomicity: implementation, version markers, generated templates, tests, documentation, and migration guidance must describe the same behavior in the same change.

Depending on the impact, the change set includes:

1. the implementation change;
2. every affected component version bump;
3. scaffold or generated-template updates;
4. tests demonstrating the changed behavior and compatibility boundary;
5. reference or workflow documentation updates;
6. scaffold synchronization or state migration behavior;
7. a changelog entry describing impact; and
8. application or operator migration instructions when existing deployments cannot continue unchanged.

A trivial compatible patch does not require every item. The maintainer should still record the compatibility assessment that justifies the selected component bump or the decision not to bump.

Several versions move together only when the same change affects several contracts. If `container_install.sh` starts calling a new common-library helper, both the common-library and container-installer versions change with their templates and tests. If Django bootstrap changes and requires a new Django-library helper, both the Django installer and Django-library versions may change. Other component versions remain unchanged.

## Current compatibility enforcement

The current version constants are informational. `container_install.sh --version` and Django `install.sh --version` print their respective `APP_VERSION`, but neither script checks the versions exported by the sourced libraries. The library constants are not compared at runtime, and no compatibility range is declared.

The scaffold synchronizes vendored libraries by exact file content rather than version negotiation. `check` and `check-lib` report missing or modified checked library copies, while `sync` and `sync-lib` replace them from the canonical `lib/container/` sources. The scaffold-state `standard_version` is written but is not currently validated when state is loaded.

Consequently, matching version numbers do not prove compatibility, and mismatched numbers do not trigger an automatic failure. Compatibility is maintained by coordinated code/templates/tests, exact library synchronization, scaffold state, and review of the selected repository commit.

## Scaffold synchronization

Generated script changes reach initialized applications through `scaffold.py sync`. Canonical library changes reach them through the library synchronization performed by `sync` or explicitly through `sync-lib`. Locally modified managed files may produce `.bu-isciii-update` candidates requiring human reconciliation.

Backward-incompatible changes need an explicit migration path or operator instructions before applications synchronize. See the [`scaffold.py` reference](scaffold.md) for exact behavior and the [Scaffold workflow](../guides/scaffold-workflow.md) for the update procedure.

## Examples

| Change | Expected classification |
| --- | --- |
| Correct a common-helper error message without changing exit behavior or output consumed by callers | Common library `PATCH` |
| Add a new optional outer-installer option with a safe default | Container installer `MINOR` |
| Rename or remove `--install_conf_map` | Container installer `MAJOR`, with migration instructions |
| Fix Django settings quoting while preserving accepted inputs and rendered meaning | Django library `PATCH` |
| Add an optional Django bootstrap hook | Django installer `MINOR`; also Django library `MINOR` only if a new shared helper is part of the contract |
| Change a profile or addon persistent-volume layout so existing data must move | `MAJOR` for any existing versioned component whose contract implements or orchestrates the change; profiles/addons have no separate version marker, so also record the repository commit and include data migration, backup, and rollback instructions |

## Test expectations

When a component version changes, tests should demonstrate the behavior that justified the bump. For compatibility-sensitive changes, cover existing descriptors or settings where feasible, scaffold synchronization, affected library calls, and the migration or failure path for breaking changes. An exhaustive cross-version matrix is not required unless the implementation begins supporting explicit compatibility ranges.
