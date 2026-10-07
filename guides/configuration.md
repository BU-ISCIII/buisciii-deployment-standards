# Configuration

Use the project descriptor to choose what the scaffold generates. Use the
generated installation settings to configure a deployment. They are separate
configuration layers.

| Layer | Main files | Change it when |
|---|---|---|
| Project descriptor | `project.json` | The service topology, profile, build context, or addons change |
| Installation settings | `conf/*settings.txt`, `conf/<addon>/*settings.txt` | An environment-specific deployment value changes |
| Build-time configuration | Selected values passed to an image build | A value compiled or staged into an image changes |
| Runtime configuration | Compose environment and mounted or copied files | A container needs a value when it starts or is bootstrapped |
| Generated runtime configuration | `.env.<mode>.file`, rendered Django or addon files | Normally never; change its source instead |

```text
project.json + selected profile/addons
                 |
                 v  scaffold
       conf/* installation settings
                 |
                 v  container_install.sh validates and renders
     protected Compose environment + runtime files
                 |
                 v
          image builds and containers
```

## Project descriptor

`project.json` is input to `scripts/scaffold.py`. It describes generation
choices such as services, profiles, build contexts, images, selected addons,
and implemented profile or addon options. It is not the application production
runtime configuration.

Keep real database passwords and other production secrets out of the project
descriptor. Put a value there only when the current descriptor schema defines
it as a scaffold choice. See the [project descriptor
reference](../reference/project-descriptor.md).

## Installation settings

The scaffold generates the main operator-editable settings under `conf/`:

- `conf/docker_test_settings.txt` and
  `conf/docker_production_settings.txt` for the repository-owned profile;
- `conf/<addon>/<addon>_test_settings.txt` and
  `conf/<addon>/<addon>_production_settings.txt` for each selected addon.

In a multi-service deployment, each service `TEST_INSTALL_CONF` and
`INSTALL_CONF` descriptor fields identify its test and production source.
`container_install.sh` accepts per-component overrides through
`--install_conf_map`.

Settings files use shell assignment syntax:

```bash
APP_PORT="8001"
DB_HOST="database.example.org"
DB_USER="example_user"
DB_PASSWORD="CHANGE_ME"
```

The exact variables depend on the selected profile and addons. Read the
generated `conf/INSTALL_SETTINGS.md` before editing them. See the
[configuration variable reference](../reference/configuration-variables.md)
for the variable dictionary.

## Test and production configuration

Test and production settings are separate inputs and produce separate Compose
models.

| | Test | Production |
|---|---|---|
| Purpose | Local or isolated deployment | Real deployment |
| Credentials | Generated disposable values may be used | Copy the template to a protected, non-committed file and supply real values |
| Data | Implemented test or demo loading may be enabled | Demo data is not loaded implicitly |
| Paths and storage | May use `/tmp` paths or disposable volumes | Uses declared persistent paths, volumes, or external services |
| Application behavior | May enable local settings such as Django debug | Uses production-safe profile settings |

Test values are not automatically safe merely because they appear in a test
file. Never reuse generated test credentials in production.

Before a production build or start, the installer rejects a selected settings
file containing an active uppercase assignment whose value includes
`CHANGE_ME`. Commented examples are not active assignments. This check does not
prove that a replacement value is correct or an external service is reachable.

## Build-time and runtime values

A build-time value affects creation of an image. A runtime value is supplied
when a container starts or when the installer bootstraps it.

React/Vite `VITE_*` values and Next.js `NEXT_PUBLIC_*` values are passed as
build arguments and embedded in browser code. Changing them requires an image
rebuild, and they must not contain secrets. Next.js server-only values such as
`AUTH_SECRET` and internal proxy targets are supplied at runtime.

Django production uses a different path. Its selected settings source is
mounted into the build as an ephemeral build secret so staging can read it
without copying it into an image layer. Production Django settings rendering
is disabled during the build and performed on the host before Compose starts.

Do not put a secret in a normal build argument. Profile-specific details belong
in the [Django](../profiles/django.md), [Next.js](../profiles/nextjs.md), and
[React/Vite](../profiles/react-vite.md) documentation.

## Sensitive values

The production settings file is a template. Copy it to a file excluded from
Git, replace its required placeholders, and restrict the copy to the deployment
operator; generated instructions use mode `0600`. Never commit real secrets.

The installer combines selected settings into `.env.production.file` (or
`.env.test.file`) at the deployment root. It creates this Compose interpolation
file atomically with mode `0600`. It may contain secrets, but it is a protected
dotenv file, not a Docker or Compose secret object.

For Django production, the implementation also:

- passes the source settings file through the engine build-secret interface;
- renders `DJANGO_SETTINGS_PATH` on the host and bind-mounts it; the current
  helper sets this generated file to mode `0664`;
- copies the selected settings to `conf/.runtime_install_settings.txt` inside
  the container for bootstrap, assigns it to the application identity, and
  sets mode `0600`; and
- removes that in-container production copy after the bootstrap attempt.

The temporary bootstrap file is not persistent configuration. The repository
does not require an external secret manager and does not route all values
through container secret objects. See the
[security requirements](../standards/security-requirements.md).

## Generated runtime configuration

Derived files should not normally be edited directly:

```text
editable installation settings
              |
              v
      installer validates/renders
              |
              v
 generated runtime configuration
              |
              v
        container consumes it
```

| Generated file | Source to edit instead |
|---|---|
| `.env.test.file` or `.env.production.file` | Selected application and addon settings files |
| Django file at `DJANGO_SETTINGS_PATH` in production | Selected production settings and `conf/template_settings.py` |
| `deployment/apache/*.conf` | `conf/apache/*.conf` and Apache installation settings |
| Keycloak realm files at `KEYCLOAK_IMPORT_PATH` | JSON under `KEYCLOAK_REALM_SOURCE_PATH` |
| Django `conf/.runtime_install_settings.txt` inside the container | Selected settings source |

The installer regenerates the Compose environment on each invocation and
rerenders production Django settings before Compose starts. Apache sources are
rendered into `deployment/apache/` before Compose validation.

## Profile and addon configuration

| Component | Configuration it owns |
|---|---|
| [Django](../profiles/django.md) | Database, Django, Gunicorn, email, bootstrap, and application settings |
| [Next.js](../profiles/nextjs.md) | Public build values and server-only runtime values |
| [React/Vite](../profiles/react-vite.md) | Public build values and Nginx runtime identity/port |
| [Apache](../addons/apache.md) | Proxy routes, forwarded values, status access, logs, and public binding |
| [Keycloak](../addons/keycloak.md) | Server/database credentials, public URL, realm import, and optional OIDC values |
| [Nextstrain](../scaffold/templates/addons/nextstrain/README.md) | Image/build inputs, public map settings, ports, and data path |
| [Samba](../scaffold/templates/addons/samba/README.md) | Disposable test-only Samba credentials |

Addon settings remain under `conf/<addon>/`; do not merge addon credentials
into an application profile settings file.

## Validating configuration

Validation happens at several boundaries:

1. `scripts/scaffold.py` validates descriptor structure, supported profiles and
   addons, unknown fields and options, and application-service references.
2. `scripts/scaffold.py check <target>` compares a generated deployment with
   its baseline. For settings, it reports missing standardized assignment names
   and duplicate local assignments while preserving local values. It also
   checks the Django settings-template placeholder contract.
3. `container_install.sh` rejects invalid or duplicate mappings, unknown mapped
   components, missing selected files, and active production `CHANGE_ME`
   assignments.
4. The Compose environment writer rejects invalid or duplicate output names
   and multiline values.
5. The installer validates the Compose model before image build or startup.
   Profiles then apply their own build, readiness, bootstrap, and smoke checks.

These checks do not by themselves prove that DNS, an external database, SMTP,
or another external service works. Complete the relevant acceptance checks.

## Recommended workflow

1. Define topology, profiles, build contexts, and addons in the project
   descriptor.
2. Generate the deployment baseline.
3. Read `conf/INSTALL_SETTINGS.md` and the selected profile/addon pages.
4. Fill test settings and run an isolated test deployment.
5. Validate with `scripts/scaffold.py check`, the installer, and its smoke test.
6. Copy production templates to separate, non-committed mode-`0600` files.
7. Replace every required production placeholder and verify cross-service
   values.
8. Run `container_install.sh`; use `--install_conf_map` for each component that
   needs an override.
9. Review Compose validation and smoke-test results before acceptance.

See also [Docker Compose](docker-compose.md), [ignore files](ignore-files.md),
and [container installer customization](container-install-customization.md).
