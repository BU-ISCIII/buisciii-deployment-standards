- [Backups and restore](backups-and-restore.md)
# Generated documentation files

The scaffold generates a common documentation structure for every application. Some text is managed by the deployment standard, while marked blocks belong to the application. Selected profiles and add-ons insert only the sections relevant to the generated topology.

The main distinction is:

- `README.md` explains how the application is designed to be installed, developed, tested, and operated.
- `LEAME.md` is the production operator runbook: it records how a specific production deployment is prepared, updated, checked, recovered, and owned.

Use this guide to decide where application information belongs. For the complete deployment procedure, follow [Deployment workflow](deployment-workflow.md).

## 1. Documentation overview

The scaffold renders both files from common templates and adds profile- and add-on-owned fragments. This keeps the deployment interface consistent without hiding framework-specific or optional-service behavior.

The files are not wholly application-owned. Edit only the named application blocks for application-specific content. If generic generated text is wrong, change the template that owns it instead of patching every generated repository.

## 2. `README.md`

The README is for developers, maintainers, and people evaluating or testing the deployment. Its information should be reusable across environments and should not contain production secrets.

The generated README includes:

- the application overview and service/profile topology;
- checkout instructions, supported deployment paths, and minimum requirements;
- protected configuration preparation;
- Docker and Podman test and production entry points;
- persistent data, proxy, application-server, and scheduled-job guidance;
- routine container operations and upgrades;
- profile-specific bare-metal instructions where supported;
- database, backup, restore, rollback, and failure guidance;
- profile- and add-on-specific operational commands;
- final application configuration, developer notes, migration guidance, and smoke-test verification;
- links to user, administrator, API, upgrade, and support documentation.

Complete the application-owned blocks described below. Keep real hostnames, deployed revisions, credentials, and production-only paths in the operational record or protected configuration rather than turning the README into an instance-specific runbook.

For configuration details, link to [Configuration](configuration.md). For the ordered release procedure, link to [Deployment workflow](deployment-workflow.md).

## 3. `LEAME.md`

`LEAME.md` keeps its BU-ISCIII-specific filename and serves as the concrete production runbook. Its audience is deployment operators, systems or IT staff, and maintainers performing upgrades or recovery.

The generated runbook is organized around the implemented rootless Podman production procedure. It covers:

- the approved revision and operational ownership;
- public exposure, dependencies, recovery objectives, and backup location;
- production host directories and declared persistent assets;
- checkout and protected configuration locations;
- host-path preparation and permission repair;
- application-specific pre-install or pre-backup steps;
- backup, upgrade, post-deployment checks, and rollback;
- smoke tests, service diagnostics, and profile/add-on operational commands;
- rootless Podman ownership and SELinux reminders.

Record actual production inputs or an auditable reference to them. Do not copy passwords, tokens, or other secret values into the runbook; point to the protected settings source instead.

An approved production runbook must not contain unresolved `CHANGE_ME` values. Generated angle-bracket command metavariables are instructions to the operator; replace them when the runbook is adopted for a deployment or make the referenced operational source unambiguous. Unfinished review markers such as `<REVISAR...>` must not remain.

Use [Upgrades and rollback](upgrades-and-rollback.md) and [Backups and restore](backups-and-restore.md) for the full shared procedures.

## 4. Application-owned documentation blocks

The scaffold recognizes blocks delimited by matching `BEGIN BU-ISCIII APPLICATION` and `END BU-ISCIII APPLICATION` comments. During synchronization, it copies the existing block body into the newly rendered file.

The common templates define these blocks:

| File | Block | Put this information here |
| --- | --- | --- |
| `README.md` | `overview` | Domain purpose, architecture link or image, user documentation, and support channel |
| `README.md` | `final-configuration` | Application-specific post-install work such as identity, email, storage, scheduled jobs, and a representative user workflow |
| `README.md` | `developer-notes` | Application development, test, and release workflows |
| `README.md` | `documentation-links` | User, administrator, API, upgrade, and support links |
| `LEAME.md` | `production-runbook` | Deployment-specific procedures required before backup or first production installation |

For example, this existing block is safe for application content:

```markdown
<!-- BEGIN BU-ISCIII APPLICATION: production-runbook -->
Application-specific operational steps.
<!-- END BU-ISCIII APPLICATION: production-runbook -->
```

Do not rename markers, duplicate a block name, or casually edit standard-managed text outside the blocks. Django's generated `conf/INSTALL_SETTINGS.md` also provides `installation-settings` and `addon-settings-notes` blocks for application-specific configuration documentation.

## 5. Profile and add-on sections

The scaffold composes documentation fragments according to the selected topology. Profiles contribute framework information such as build/runtime behavior, persistence, local testing, migrations, bare-metal installation, and operational commands. For example, Django contributes migration, bootstrap, static-file, and diagnostic commands; frontend profiles contribute their applicable build/runtime and persistence guidance.

Add-ons contribute only their relevant sections. Current examples include Apache operations, Keycloak operations and backup/restore commands, Nextstrain data and persistence operations, and Samba test-data guidance.

If information applies to every application using a profile or add-on, update that profile or add-on documentation template. Do not copy the same generic text into each application's owned blocks.

Use this ownership decision:

```text
Is the information specific to one application or deployment?
    -> application-owned documentation block or LEAME.md value

Does it apply to every application using a profile?
    -> profile documentation template

Does it apply to an add-on?
    -> add-on documentation template

Does it apply to all deployments?
    -> common documentation template or standard
```

## 6. What information belongs where

| Information | `README.md` | `LEAME.md` |
| --- | --- | --- |
| Application purpose and general topology | Yes | Short production-specific topology |
| Developer and local-test workflow | Yes | No |
| Supported installation paths | Yes | Only the adopted production path |
| Production hostname and public URL | Generic reference only | Actual value or controlled reference |
| Real production paths and service account | Usually no | Yes |
| Deployed revision and image evidence | No | Yes |
| Persistent assets | General inventory and policy | Actual locations and recovery evidence |
| Backup, restore, and rollback | Reusable summary and links | Executable production record |
| Troubleshooting | Reusable application guidance | Production diagnostics and escalation |
| Passwords, tokens, and secret values | No | No; reference protected configuration |

## 7. Keep documentation synchronized

Standard-managed documentation can change when the selected standards revision changes. Run `scaffold.py check` to detect generated-file or contract drift and `scaffold.py sync` to apply supported updates. Application-owned block bodies are preserved.

If managed text was edited locally, synchronization can write a `.bu-isciii-update` candidate for manual review. Move application-specific content into the appropriate owned block, resolve the managed difference, and check again.

See [Scaffold workflow](scaffold-workflow.md) for commands, statuses, conflict handling, and shared-library synchronization.

## 8. Documentation checklist

For `README.md`, verify that:

- the application and topology description is correct;
- prerequisites and supported paths are current;
- test and installation commands match the generated deployment;
- configuration references are correct;
- profile and add-on behavior is documented in the owning layer;
- application-owned sections contain the required reusable guidance.

For `LEAME.md`, verify that:

- production host, DNS, ownership, and dependency information is complete;
- protected configuration and persistent paths are correct;
- production install and upgrade commands are current;
- backup, restore, rollback, validation, and diagnostics are usable;
- the deployed revision and resulting evidence can be recorded;
- no unresolved `CHANGE_ME` or review marker remains;
- no secret value is written directly into the document.

Finally, run the scaffold synchronization check described in [Deployment workflow](deployment-workflow.md) before approving the documentation.
