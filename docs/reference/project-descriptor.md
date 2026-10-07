# Project descriptor

`project.json` describes scaffold topology and generation choices: application identity, services, profiles, build contexts, and add-ons. It is not a production runtime settings file. Runtime ports, credentials, host paths, and service URLs belong in generated installation settings; see [Configuration](../guides/configuration.md).

The scaffold stores the descriptor in `.bu-isciii-deployment/state.json`, so later `check` and `sync` commands can reuse it.

## 1. Minimal example

This is the current single-service shape from `scaffold/project.json.example`, shortened only by omitting fields that generation does not require:

```json
{
  "APP_NAME": "Example Application",
  "APP_SLUG": "example-app",
  "DESCRIPTION": "Describe what the application does.",
  "REPOSITORY_URL": "https://github.com/BU-ISCIII/example-app.git",
  "PYTHON_VERSION": "3.11",
  "TIMEZONE": "Europe/Madrid",
  "SERVICES": {
    "example-app": {
      "PROFILE": "django",
      "BUILD_CONTEXT": ".",
      "INSTALL_CONF": "conf/docker_production_settings.txt",
      "TEST_INSTALL_CONF": "conf/docker_test_settings.txt",
      "PROJECT_MODULE": "example_app"
    }
  },
  "ADDONS": {}
}
```

## 2. Project-level fields

The parser does not currently enforce a top-level key whitelist. It passes scalar string, number, and boolean values to templates and stores the complete object in scaffold state. The fields below are the implemented public inputs; extra top-level metadata is not guaranteed to affect output.

| Field | Required | Type | Purpose/default |
| --- | ---: | --- | --- |
| `APP_NAME` | Yes | String | Human-readable name used in generated scripts and documentation |
| `APP_SLUG` | Yes | String | Deployment identifier used in paths and add-on service names |
| `DESCRIPTION` | Yes | String | Initial application overview in `README.md` |
| `REPOSITORY_URL` | No | String | Clone URL in generated documentation; defaults there to `<repository-url>` |
| `DEFAULT_BRANCH` | No | String | Present in supplied examples, but currently stored only and not consumed by generation |
| `PYTHON_VERSION` | Django root profile | String | Python version rendered into Django root artifacts |
| `TIMEZONE` | Django root profile | String | Time zone rendered into Django root artifacts |
| `SERVICES` | Yes | Object | Non-empty mapping of stable service names to service objects |
| `ADDONS` | No | Object, array, or comma-separated string | Selected add-ons; defaults to an empty object |
| `GENERATE_PROFILE_ARTIFACTS` | No | Boolean | When exactly `false`, suppresses root profile artifacts; defaults to enabled |

Missing values required by a selected template fail rendering. Because unknown top-level keys are accepted, successful parsing does not mean an arbitrary field has behavior.

## 3. `SERVICES`

`SERVICES` is a non-empty object keyed by deployment service name. Names must match:

```text
[a-z0-9][a-z0-9_-]*
```

A service key becomes a Compose service identity and may be used in container-network hostnames, generated environment prefixes, volume names, and documentation. Keep it stable across standalone and orchestrated descriptors.

A standalone project normally has one service with `BUILD_CONTEXT: "."`. An orchestrator can declare multiple local or sibling contexts. At most one service may use `.` or `./`; that service owns root profile artifacts such as `Dockerfile` and `conf/`. The compiler orders that owned service first.

## 4. Service fields

Each service value must be a JSON object. Unknown service keys are rejected.

| Field | Required | Type | Applies to | Meaning/default |
| --- | ---: | --- | --- | --- |
| `PROFILE` | Yes | String | All | `django`, `nextjs`, or `react-vite`; normalized to lowercase |
| `BUILD_CONTEXT` | Yes | String | All | Compose/image build context; `.` or `./` marks the repository-owned service |
| `DOCKERFILE` | No | String | All | Dockerfile relative to its build context; defaults to `Dockerfile` |
| `IMAGE` | No | String | All | Image name; defaults to `<service-name-with-hyphens>:local` |
| `INSTALL_CONF` | Yes | String | All | Default production installation-settings source |
| `TEST_INSTALL_CONF` | Yes | String | All | Default test installation-settings source |
| `PROJECT_MODULE` | Django only | String | Django | Required Django project-module name; rejected for other profiles |
| `API` | No | Boolean | Django | Enables generated optional API settings; defaults to `false` and is rejected for other profiles |
| `DATABASE` | No | String | Django | `external` or `compose`; defaults to `external`; explicitly setting it on another profile is rejected |

Most service values are converted to strings internally, but descriptors should use the documented string types. `API` must be a JSON boolean.

## 5. Profiles

A profile selects framework-owned build, Compose, settings, readiness, bootstrap, health, and documentation fragments.

| Value | Root artifacts | Details |
| --- | --- | --- |
| `django` | Django Dockerfile, installer, settings, health package, startup script, migration guide | [Django](../profiles/django.md) |
| `nextjs` | Next.js Dockerfile, settings, startup script, Pages-router health endpoint | [Next.js](../profiles/nextjs.md) |
| `react-vite` | React/Vite Dockerfile, settings, Nginx configuration, startup script | [React/Vite](../profiles/react-vite.md) |

The profile must correspond to an existing supported profile directory; arbitrary profile names are rejected.

## 6. Database and API options

For Django, `DATABASE: "external"` keeps the production database outside the generated Compose topology. `DATABASE: "compose"` adds a production database service and persistent database volume. Django test topology includes its disposable Compose-managed database support in either case.

`API: true` adds the current Django API configuration fragments and Compose environment. It does not create a generic API service and is not valid for frontend profiles.

Database passwords, connection endpoints, API credentials, and other runtime values remain in installation settings.

## 7. `ADDONS`

The accepted forms are:

```json
{"apache": {}, "keycloak": {}}
```

```json
["apache", "keycloak"]
```

```json
"apache,keycloak"
```

Use object form to set options. Names are normalized to lowercase and must match a current directory under `scaffold/templates/addons/`: `apache`, `keycloak`, `mailpit`, `nextstrain`, or `samba`.

Array and comma-separated forms select add-ons with default options. An object value may be `null`, which is treated as an empty options object.

## 8. Add-on options

Unknown add-on options are rejected.

| Option | Type | Applies to | Meaning/default |
| --- | --- | --- | --- |
| `CONFIG_SERVICE` | String | All add-ons | Application service whose configuration context the add-on uses; defaults to the first normalized service |
| `MODES` | Non-empty array | All add-ons | Enabled Compose modes; accepts `prod`, `production`, and `test`; defaults to both `prod` and `test`, with `production` normalized to `prod` |
| `MOUNTS` | Array | All add-ons | Optional mount strings consumed when the add-on supplies an application-mount template; currently used by Apache and Keycloak |
| `OIDC_SERVICES` | Array | Keycloak | Django services receiving Keycloak OIDC settings; defaults to the configuration service only when that service is Django, otherwise empty |
| `ADMIN_ACCESS` | Boolean | Keycloak | Adds Keycloak administrative-access settings to the configured Django consumer when applicable; defaults to `false` |

`CONFIG_SERVICE` and every `OIDC_SERVICES` entry must name a declared service. Keycloak OIDC consumers must currently use the Django profile. Duplicate mode and OIDC entries are removed while preserving their first occurrence.

`MODES` controls whether the add-on service is included in test and/or production Compose. Add-on source settings are still generated for the selected add-on.

## 9. Examples

### Standalone Django

```json
{
  "APP_NAME": "Sample Registry",
  "APP_SLUG": "sample-registry",
  "DESCRIPTION": "Registry service.",
  "REPOSITORY_URL": "https://example.invalid/sample-registry.git",
  "PYTHON_VERSION": "3.11",
  "TIMEZONE": "Europe/Madrid",
  "SERVICES": {
    "sample-registry": {
      "PROFILE": "django",
      "BUILD_CONTEXT": ".",
      "INSTALL_CONF": "conf/docker_production_settings.txt",
      "TEST_INSTALL_CONF": "conf/docker_test_settings.txt",
      "PROJECT_MODULE": "sample_registry"
    }
  },
  "ADDONS": {}
}
```

### Multi-service orchestrator

```json
{
  "APP_NAME": "Research Portal",
  "APP_SLUG": "research-portal",
  "DESCRIPTION": "Frontend and API deployment.",
  "SERVICES": {
    "portal-web": {
      "PROFILE": "react-vite",
      "BUILD_CONTEXT": ".",
      "INSTALL_CONF": "conf/docker_production_settings.txt",
      "TEST_INSTALL_CONF": "conf/docker_test_settings.txt"
    },
    "registry-api": {
      "PROFILE": "django",
      "BUILD_CONTEXT": "../registry-api",
      "INSTALL_CONF": "../registry-api/conf/docker_production_settings.txt",
      "TEST_INSTALL_CONF": "../registry-api/conf/docker_test_settings.txt",
      "PROJECT_MODULE": "registry_api",
      "DATABASE": "compose"
    }
  },
  "ADDONS": {
    "apache": {
      "CONFIG_SERVICE": "portal-web",
      "MODES": ["prod", "test"]
    },
    "keycloak": {
      "CONFIG_SERVICE": "portal-web",
      "OIDC_SERVICES": ["registry-api"]
    }
  }
}
```

## 10. Validation rules

The scaffold enforces these descriptor rules:

- `SERVICES` is a non-empty object.
- Service names follow the implemented pattern and service values are objects.
- Service keys are limited to the fields documented above.
- Required service fields are non-empty after normalization.
- Profiles and profile-only fields are validated.
- At most one service uses the repository root as its build context.
- Add-on names, options, modes, and service references are validated.
- `MOUNTS` and `OIDC_SERVICES` have array types; `ADMIN_ACCESS` is boolean.
- Required template values must exist before rendering.
- `init` refuses a target already containing scaffold state.
- During `check` or `sync`, changing between a repository-owned profile shape and a multi-service-only shape is rejected.
- Changing the repository-owned framework profile during synchronization is rejected because it would mix incompatible generated artifacts.

See [Creating a project](../guides/creating-a-project.md) for the creation workflow and [Generated project structure](generated-project-structure.md) for output ownership.

## 11. What does not belong here

Do not use the descriptor for values owned by installation or runtime configuration, including:

- database passwords and other production secrets;
- application UID/GID and ports;
- production database, email, identity, or proxy credentials;
- persistent host paths;
- public hostnames and URLs unless a future explicitly documented descriptor option owns them;
- values generated into `.env.test.file` or `.env.production.file`.

Put those values in the generated test settings or protected production settings described by [Configuration](../guides/configuration.md). The descriptor selects what to generate; installation settings configure a deployment.
