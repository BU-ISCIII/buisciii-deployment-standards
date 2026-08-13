# BU-ISCIII Deployment Standards

This repository defines a shared standard and a working deployment baseline for
BU-ISCIII applications. It is intentionally independent of any particular
application. The scaffold currently provides complete `django` and
`react-vite` profiles; framework-specific files are never mixed.

The standard is meant to answer one practical question:

> What must an application provide before its installation procedure can be
> considered complete, reproducible, and safe for production?

## Create a new application baseline

Copy and fill the project descriptor:

```bash
cp scaffold/project.json.example /tmp/my-application.json
```

For a baseline that demonstrates Apache and Keycloak configuration, use the
complete add-on example instead:

```bash
cp scaffold/project.addons.json.example /tmp/my-application.json
```

Every project uses the same schema. Keep one `SERVICES` entry for a standalone
application, or add entries for an orchestrator. Each service independently
selects `PROFILE` as `django` or `react-vite`; `ADDONS` may be empty.
Set optional `API: true` only on Django services that need the standard API
configuration contract. When the Keycloak add-on selects a Django service with
`CONFIG_SERVICE`, the scaffold also adds the application-side OIDC validation
settings to that service; these are distinct from the Keycloak server settings.
The one service using `BUILD_CONTEXT: "."` owns this repository's profile
artifacts such as its Dockerfile and inner installer. Other services reference
their own application repositories through external build contexts.

Generate the baseline in a new or existing application repository:

```bash
python3 scripts/scaffold.py init /path/to/my-application \
  --config /tmp/my-application.json
```

For an orchestrator, add the remaining application entries and select Apache
or Keycloak under `ADDONS`. The generator assembles all selected fragments into
exactly one production and one test Compose file.

The generator creates concrete installation documentation, scripts, settings,
Docker files, Compose files, and a smoke test. Review every generated file and
complete the application-specific tasks in the checklist.

## Synchronize improvements into an application

Run the synchronizer from an updated checkout of this repository:

```bash
python3 scripts/scaffold.py sync /path/to/my-application
```

The application configuration and baseline checksums are stored under
`.bu-isciii-deployment/state.json` in the application repository.
The complete nested `SERVICES`/`ADDONS` descriptor is recorded there. A
standalone repository cannot change its owned framework profile through `sync`
because that would mix incompatible profile artifacts; multi-service projects
can evolve service declarations through normal conflict-aware synchronization.

- Unmodified generated files are updated automatically.
- New baseline files are added automatically.
- Locally modified files are never overwritten.
- A conflicting new version is written beside the local file with the suffix
  `.bu-isciii-update` for manual comparison and merge.

After resolving a candidate, remove the `.bu-isciii-update` file and run the
application tests. This mechanism is intentionally small and does not require a
package manager, CI service, or third-party template tool.

### Synchronize only the shared container library

Mature applications should synchronize the centrally owned library without
generating complete application-file candidates:

```bash
python3 scripts/scaffold.py check-lib /path/to/application
python3 scripts/scaffold.py sync-lib /path/to/application
```

`check-lib` is read-only and exits non-zero when a shared file is missing or
modified. `sync-lib` replaces only files below `deployment/lib` from the
canonical `lib` directory. Applications must not edit vendored shared files;
custom behavior belongs in their `container_install.sh` wrapper.

## Review the standard

1. Read [the installation contract](standards/application-installation-contract.md).
2. Select only the technology profiles that apply to the application.
3. Complete the installation checklist during the application audit.
4. Keep application-specific commands, ports, paths, and recovery procedures in
   the application repository.
5. Record intentional exceptions instead of silently diverging from the
   contract.

This repository owns common requirements and templates. It does not replace an
application's installation guide or an orchestrator's production runbook.

## Repository contents

- `standards/`: requirements applying to all applications.
- `profiles/`: additional guidance for particular technologies.
- `lib/`: exactly synchronized, application-neutral deployment libraries.
- `scaffold/`: files rendered into a new application repository.
- `scaffold/templates/common/`: the shared outer installer, documentation,
  Compose document, ignore policy and smoke dispatcher.
- `scaffold/templates/profiles/`: framework-owned Dockerfiles, inner installers,
  entrypoints and configuration; selected independently per service.
- `scaffold/templates/addons/`: optional Compose components, kept separate from
  framework profiles and assembled into the final single Compose file.
- `scripts/scaffold.py`: initialization and safe synchronization command.
- `templates/`: detailed audit and configuration-review documents. The generated
  `LEAME.md` is the concrete production runbook.
- `audits/`: dated application assessments and validation findings.

Current audit:

- [RELECOV Platform and iSkyLIMS compliance audit](audits/relecov-compliance-2026-08-04.md)
- `CHANGELOG.md`: changes to the standard.

## Initial scope

Version 0.1 is a draft for review against PathoCore and RELECOV. It deliberately
does not include shared CI enforcement. That can be added after the scaffold has
been exercised against the real repositories.

## Language

Normative requirements use these terms:

- **MUST**: required for compliance.
- **SHOULD**: recommended unless there is a documented reason not to follow it.
- **MAY**: optional.
