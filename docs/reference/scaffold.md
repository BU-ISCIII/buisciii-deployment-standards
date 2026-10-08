# `scaffold.py` reference

## Purpose

`scripts/scaffold.py` is the repository CLI for initializing generated deployment files, checking an initialized baseline, synchronizing it with the current templates, and checking or replacing vendored shared deployment libraries.

The [Scaffold workflow](../guides/scaffold-workflow.md) explains the recommended maintenance procedure. This page defines the exact CLI behavior. Descriptor fields are documented in [Project descriptor](project-descriptor.md), and generated-file ownership is documented in [Generated project structure](generated-project-structure.md).

## Command summary

| Command | Purpose | Writes files? | Uses saved state? |
| --- | --- | ---: | ---: |
| `init` | Create the generated baseline from an explicit descriptor | Yes | Rejects a target that already has scaffold state |
| `check` | Compare generated files and shared shell libraries with the current standard | No | Yes; required |
| `sync` | Apply compatible template changes and synchronize shared libraries | Yes | Yes by default; an explicit descriptor may replace the saved configuration |
| `refresh-state` | Verify supported custom-block edits against the previous standard and refresh their hashes | State only | Yes; required |
| `check-lib` | Compare vendored shared shell libraries with their canonical sources | No | No |
| `sync-lib` | Replace missing or changed vendored shared shell and Python libraries | Yes | No |

The CLI exposes no other public subcommands.

## `refresh-state`

```text
python3 scripts/scaffold.py refresh-state TARGET [--baseline-ref COMMIT_OR_TAG]
```

Run this after every supported application-owned block edit, before `sync`, regardless of whether the current standard has changed. After successful verification, run `sync`, then `check`, review the diffs, and commit the customization with the updated state. Repeat refresh if you edit a block again. This workflow applies to recognized custom blocks; ordinary application files and schema-managed setting values do not need this hash refresh. See the [practical workflow example](../guides/scaffold-workflow.md#practical-example-repair-a-demo-data-hook).

This command requires initialized state with configuration and file hashes. It resolves the saved `standard_revision` in the current standards repository's local Git history, exports that commit into a temporary directory, and runs its historical scaffold renderer with the saved configuration. It does not switch the current checkout or fetch history. Only trusted revisions should be used because their Python code is executed.

For every historical artifact with recognized application-owned blocks, it preserves the current local block bodies and requires the resulting bytes to equal the local file. Missing files, untracked baseline paths, or differences outside the block bodies cause failure before any state is written. After all eligible files pass, it refreshes their whole-file hashes and records the resolved revision. Other hashes, state metadata, application files, libraries, and update candidates remain unchanged. It does not validate or refresh unrelated managed files or schema-managed settings.

An older state without a revision requires `--baseline-ref` identifying its actual previous standard. If a revision is already recorded, an explicit reference must resolve to that same commit. Missing history and historical rendering errors fail with exit `1`. Success exits `0`. A previous partial sync can mix baselines from different revisions; refresh refuses custom-block files whose managed sections no longer match the recorded commit. Resolve those candidates manually rather than overriding the saved revision.

Run `sync` next to apply the current standard. An accepted baseline takes precedence over a candidate left by an earlier conflict, allowing the verified update to proceed. Remove stale candidates after checking the resulting deployment baseline. See the [workflow examples](../guides/scaffold-workflow.md#understand-the-three-versions).

## `init`

```text
python3 scripts/scaffold.py init TARGET --config PROJECT_JSON
```

`TARGET` is the application repository or directory to initialize. `--config` is required by command dispatch even though the generic argument parser displays it as optional. The target may already exist; otherwise `init` creates it. Initialization fails if `TARGET/.bu-isciii-deployment/state.json` already exists and directs the caller to use `sync`.

The command loads the descriptor as a JSON object, validates it while selecting and rendering services, profiles, addons, configuration, Compose topology, and documentation, and then applies the same artifact synchronization rules used by `sync`. It creates required parent directories, writes missing generated files, preserves recognized application-owned block bodies in pre-existing files, marks generated scripts executable when it writes them through the normal managed-file path, writes scaffold state, and synchronizes the shared deployment library.

Existing files are not assumed to be disposable. If an existing managed file differs from the generated result outside a recognized application-owned block and there is no saved baseline, `init` leaves it in place, writes the generated result beside it as `FILE.bu-isciii-update`, and exits with unresolved issues. Unrelated files are not inspected or removed.

Successful initialization records the descriptor configuration and generated-file baselines in `.bu-isciii-deployment/state.json`. See [Saved state](#saved-state).

## `check`

```text
python3 scripts/scaffold.py check TARGET
```

`check` is read-only. It requires saved configuration in `TARGET/.bu-isciii-deployment/state.json`; the parser does not accept `--config` for this command. It renders the expected artifacts from the saved descriptor, preserves recognized application-owned block bodies for comparison, evaluates each generated artifact against its saved baseline and current template contract, reports paths saved by the previous baseline that are no longer generated as `obsolete`, and then calls the shared-library check.

The command checks managed-file content, application-block structure, schema-managed shell setting names, schema-managed JSON object keys, the Django settings-template contract, missing generated files, obsolete recorded paths, and shared shell-library copies. It does not assess operational or standards compliance.

A completely current baseline exits `0`. Any non-`current` generated artifact, any `obsolete` recorded path, or any missing or modified checked shared library increments the issue count and makes the command exit `1`.

## `sync`

```text
python3 scripts/scaffold.py sync TARGET [--config PROJECT_JSON]
```

Without `--config`, `sync` uses the descriptor stored in scaffold state. With `--config`, it loads that descriptor and stores it in state after synchronization. If neither source exists, argument processing fails.

For ordinary managed files, `sync` writes files that are missing or safely `update-available`. It preserves recognized application-owned block bodies before comparing or writing content. When managed content was changed locally, it leaves the local file unchanged and writes or refreshes `FILE.bu-isciii-update` with the current generated result. The candidate remains a durable marker until the local file is reconciled.

Schema-managed shell settings retain existing values and application-only assignments; `sync` appends missing standard assignments. Schema-managed JSON retains existing scalar values, arrays, and additional properties; `sync` recursively adds missing standard object properties. Duplicate setting assignments, invalid JSON, duplicate JSON properties, required object/scalar conflicts, and Django settings-template contract failures are reported as `contract-drift` and are not repaired automatically.

After processing generated artifacts, `sync` writes scaffold state and calls the same replacement operation as `sync-lib`, ensuring the generated installer is not left with missing or stale shared helpers. It returns `2` while managed drift or contract drift remains unresolved; compatible updates and shared-library replacements do not by themselves make it fail.

An explicit descriptor may change services, addons, and other supported values while keeping the initialized deployment shape compatible. Once state contains generated-file baselines, `check` and `sync` reject a change between `multi-service` and a repository-owned profile, or between different repository-owned profiles. Initialize another target for such a structural migration.

`check` may report a previously recorded path as `obsolete`. `sync` does not delete that file: it omits the path from the new state, leaving the existing file for human review. After state is rewritten, later checks no longer classify that untracked path as an obsolete generated artifact.

## `check-lib`

```text
python3 scripts/scaffold.py check-lib TARGET
```

`check-lib` is read-only and does not read scaffold state or a project descriptor. It compares every canonical `*.sh` file below `lib/container/` with the corresponding path below `TARGET/deployment/lib/container/`.

Each path is reported as `current`, `missing`, or `modified`. The command exits `0` when every checked shell file is current and `1` when one or more are missing or modified. The full `check` command includes this same shared shell-library validation after checking generated artifacts.

Vendored files under `deployment/lib/**` are centrally owned exact copies and must not be edited in an application repository.

## `sync-lib`

```text
python3 scripts/scaffold.py sync-lib TARGET
```

`sync-lib` does not read scaffold state or a descriptor. It copies every canonical `*.sh` and `*.py` file below `lib/container/` to the matching path below `TARGET/deployment/lib/container/`. Current files are left unchanged; missing or different files are replaced with canonical content.

`sync-lib` replaces centrally owned vendored library files. It does not preserve local edits, remove extra files, or update `.bu-isciii-deployment/state.json`. Successful completion exits `0`, including when no file needed an update.

## Configuration resolution and fallback

Configuration is resolved by command:

```text
init
  explicit --config required

check
  saved state configuration required

sync
  explicit --config supplied? -> load that descriptor
  otherwise saved state has config? -> use saved configuration
  otherwise -> argument error

check-lib / sync-lib
  no descriptor or saved configuration used
```

An explicit descriptor is resolved to an absolute path and must contain a JSON object. Descriptor validation occurs as the scaffold normalizes and renders the selected topology. `sync --config` takes precedence over saved configuration. `check` cannot be used to preview an alternate descriptor.

## Saved state

The state file is:

```text
.bu-isciii-deployment/state.json
```

It records:

- `standard_version`, currently `0.1.0`;
- optional `standard_revision`, the exact Git commit for reproducible accepted standard sources;
- `source`, currently `BU-ISCIII deployment standards`;
- `config`, the descriptor object loaded for the successful `init` or latest `sync`; and
- `files`, a mapping of generated artifact paths to SHA-256 baseline hashes.

The hashes cover scaffold-generated artifacts after recognized application-owned blocks have been preserved. Shared-library hashes are not stored in state; library commands compare canonical and vendored files directly.

`init` and `sync` record the current commit when there are no unresolved scaffold issues and `scripts/`, `scaffold/`, and `lib/` have no tracked or untracked Git changes. Non-Git copies and dirty source checkouts omit the revision on success. With unresolved issues, they retain the previous revision if one exists; they do not label a partial sync as fully accepted. Existing state needs no manual format migration. `standard_version` is not a substitute for the exact revision.

The state enables future `check` and descriptor-free `sync` operations and distinguishes local managed edits from central template changes. It should normally remain under version control with the generated deployment baseline. Do not edit it manually. The meaning and current enforcement limit of `standard_version` are documented in [Deployment component versioning](versioning.md).

## Synchronization statuses

Ordinary-file comparisons use whole-file hashes after preserving local application-owned blocks in the rendered result. A supported custom edit combined with a standard update can therefore be reported as `managed-drift-with-update`. Use `refresh-state` to verify and accept only that custom edit against the previous revision; see the [A/B/C comparisons](../guides/scaffold-workflow.md#understand-the-three-versions). A candidate matching the generated result keeps unresolved drift visible unless the local file already matches the generated result or the accepted baseline.

| Status | Meaning | `sync` behavior | Human action |
| --- | --- | --- | --- |
| `current` | The current artifact satisfies its ownership contract and current generated result. For schema-managed files, local values may differ while the required schema remains present. | Leaves the file unchanged. | None. |
| `update-available` | A normal managed file still matches its saved baseline but the current generated result changed, or a schema-managed file lacks required standard entries. | Replaces a normal managed file; merges missing shell assignments or JSON properties into schema-managed files. | Review the applied change. |
| `managed-drift-without-update` | Managed content differs locally while the saved central baseline still equals the current generated result. | Preserves the local file and writes the generated result to `.bu-isciii-update`; exits `2`. | Reconcile the local edit with a supported ownership boundary. |
| `managed-drift-with-update` | Managed content differs locally and the generated result also changed since the saved baseline. | Preserves the local file and writes the current generated result to `.bu-isciii-update`; retains the previous baseline for that path and exits `2`. | Merge supported application content, restore managed content, remove the candidate, and rerun. |
| `contract-drift` | A structured artifact violates its required schema or structural contract. | Reports details without automatically repairing the artifact; exits `2`. | Repair the reported contract problem and rerun. |
| `missing` | A required generated artifact does not exist. | Creates it with current generated content. | Review the restored file. |
| `obsolete` | A path exists in saved baselines but is no longer generated by the selected descriptor and standard. This status is produced by `check`. | Does not delete the file; the next state omits the path. | Review and remove or retain the now application-owned/untracked file deliberately before synchronization. |

Shared-library checks use the separate statuses `current`, `missing`, and `modified`. Library synchronization reports `current` or `updated`.

Application-owned block bodies are inserted into the current generated result before ordinary managed-file classification. Duplicate recognized block names fail processing. Schema-managed settings and JSON use their specific contract rules rather than byte-for-byte managed-file classification.

## Exit behavior

| Situation | Exit code |
| --- | ---: |
| Successful `init`, `sync`, or `sync-lib` with no unresolved generated-file issue | `0` |
| Successful `check` or `check-lib` with no drift | `0` |
| Successful `refresh-state` verification and state refresh | `0` |
| `refresh-state` lacks a usable historical revision or cannot verify custom-block files | `1` |
| `check` finds generated-file, obsolete-path, or checked shared-library drift | `1` |
| `check-lib` finds a missing or modified checked library | `1` |
| File, JSON, descriptor, rendering, topology, or operating-system error caught by the CLI | `1` |
| `init` or `sync` completes but leaves managed drift or contract drift unresolved | `2` |
| Argument-parser error, including a missing required configuration source or initializing an already initialized target | `2` |

The CLI writes caught filesystem, validation, and JSON errors to standard error as `Error: ...`. Argument parsing writes usage and its error to standard error. Status lines and summaries are written to standard output. `--help` exits `0`.

## File ownership interaction

Fully managed files are compared with their saved baseline. Files with recognized application-owned blocks are compared after those block bodies are carried into the current generated result. Schema-managed settings and JSON preserve local values while enforcing required names or object keys. The application-owned Django settings template preserves application code while enforcing renderer placeholders and required structural assignments. Files that are not generated artifacts are not inspected. Centrally owned library copies are compared or replaced independently of scaffold state.

See [Generated project structure](generated-project-structure.md) for the ownership classes and the [Scaffold workflow](../guides/scaffold-workflow.md) for conflict resolution.

## Examples

```bash
# Initialize a baseline.
python3 scripts/scaffold.py init ./my-project --config ./project.json

# Check it using the descriptor saved during initialization.
python3 scripts/scaffold.py check ./my-project

# Synchronize it using saved configuration.
python3 scripts/scaffold.py sync ./my-project

# Synchronize it while adopting a reviewed descriptor change.
python3 scripts/scaffold.py sync ./my-project --config ./project.json

# Check or replace only the vendored shared library.
python3 scripts/scaffold.py check-lib ./my-project
python3 scripts/scaffold.py sync-lib ./my-project
```

## Automation considerations

`check` and `check-lib` are suitable for CI because they are read-only. Exit `0` means that the checked scope is current; exit `1` means that the reported scope needs an update or human intervention. Neither command proves full deployment compliance.

`sync` and `sync-lib` mutate the target. Run them in automation only when repository changes are intentional and reviewed. A `sync` exit of `2` means generated candidates or contract problems still require human action. Automation should retain command output and inspect any `.bu-isciii-update` candidates rather than treating file creation as resolution.
