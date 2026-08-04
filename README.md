# BU-ISCIII Deployment Standards

This repository defines a shared standard and a working deployment baseline for
BU-ISCIII applications. It is intentionally independent of any particular
application, while the first scaffold targets the Django/Gunicorn/MySQL pattern
used by RELECOV Platform.

The standard is meant to answer one practical question:

> What must an application provide before its installation procedure can be
> considered complete, reproducible, and safe for production?

## Create a new application baseline

Copy and fill the project descriptor:

```bash
cp scaffold/project.json.example /tmp/my-application.json
```

Generate the baseline in a new or existing application repository:

```bash
python3 scripts/scaffold.py init /path/to/my-application \
  --config /tmp/my-application.json
```

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

- Unmodified generated files are updated automatically.
- New baseline files are added automatically.
- Locally modified files are never overwritten.
- A conflicting new version is written beside the local file with the suffix
  `.bu-isciii-update` for manual comparison and merge.

After resolving a candidate, remove the `.bu-isciii-update` file and run the
application tests. This mechanism is intentionally small and does not require a
package manager, CI service, or third-party template tool.

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
- `scaffold/`: files rendered into a new application repository.
- `scripts/scaffold.py`: initialization and safe synchronization command.
- `templates/`: detailed audit and configuration-review documents. The generated
  `LEAME.md` is the concrete production runbook.
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
