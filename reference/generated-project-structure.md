# Generated project structure

This reference maps scaffold-generated source files to their purpose and ownership. Exact output depends on the selected profile, add-ons, and whether the repository owns a local profile service or only coordinates external services. Not every project receives every file.

See [Creating a project](../guides/creating-a-project.md) and [Scaffold workflow](../guides/scaffold-workflow.md) for procedures.

## 1. Overview

A typical repository-owned profile produces:

```text
README.md
LEAME.md
container_install.sh
Dockerfile
docker-compose.test.yml
docker-compose.prod.yml
.gitignore
.dockerignore
conf/
  INSTALL_SETTINGS.md
  docker_test_settings.txt
  docker_production_settings.txt
scripts/
  container_start.sh
  smoke_test.sh
deployment/lib/container/
.bu-isciii-deployment/state.json
```

Profiles and add-ons add the conditional files below. A multi-service repository without a service whose build context is `.` does not receive root profile artifacts such as `Dockerfile`, profile settings, or `scripts/container_start.sh`. It still receives common documentation, the installer, Compose files, smoke test, selected add-on sources, shared library, and scaffold state.

Template-only `compose/`, `container_install/`, `documentation/`, and `settings_fragments/` directories are compiler inputs, not generated application directories.

## 2. Common files

| Path | Purpose | Ownership |
| --- | --- | --- |
| `README.md` | Application and deployment guide assembled from common, profile, and add-on fragments | Standard-managed; edit named `BU-ISCIII APPLICATION` blocks only |
| `LEAME.md` | Production operator runbook | Standard-managed; edit the `production-runbook` block only |
| `container_install.sh` | Host-side install, upgrade, permission-repair, bootstrap, and verification entry point | Standard-managed except for `deployment-hooks` |
| `docker-compose.test.yml` | Complete test topology | Fully generated |
| `docker-compose.prod.yml` | Complete production topology | Fully generated |
| `.gitignore` | Git exclusion policy for protected and runtime files | Fully generated |
| `.dockerignore` | Image build-context exclusion policy | Fully generated |
| `scripts/smoke_test.sh` | Common Compose checks plus generated profile checks | Fully generated |
| `conf/INSTALL_SETTINGS.md` | Profile settings reference with selected add-on fragments | Standard-managed except for explicit application blocks |
| `conf/docker_test_settings.txt` | Test values for the repository-owned profile | Schema-managed: standard names, application-maintained values |
| `conf/docker_production_settings.txt` | Production template for the repository-owned profile | Schema-managed: standard names, application-maintained values |

The `conf/` entries are conditional on a repository-owned profile. See the [script references](scripts/README.md) and [Generated documentation files](../guides/documentation-files.md).

## 3. Profile-specific files

Root profile artifacts appear only when one service uses build context `.` or `./` and profile-artifact generation is enabled.

### Django

| Path | Purpose | Ownership |
| --- | --- | --- |
| `Dockerfile` | Django image build | Fully generated |
| `install.sh` | Django staging and bootstrap | Standard-managed except for `install-hooks` |
| `scripts/container_start.sh` | Container startup | Fully generated |
| `conf/template_settings.py` | Application settings used by the renderer | Application-owned with structural checks |
| `conf/urls.py` | Required health route | Standard-managed except for `django-url-imports` and `django-url-routes` |
| `deployment_health/{__init__.py,views.py,urls.py,README.md}` | Health endpoint implementation and integration notes | Fully generated |
| `.github/DJANGO_MIGRATIONS.md` | Migration workflow | Fully generated |

The migration guide is also emitted for a multi-service topology containing Django when that service lives in another build context. See the [Django profile](../profiles/django.md).

### React/Vite

| Path | Purpose | Ownership |
| --- | --- | --- |
| `Dockerfile` | Frontend build and Nginx runtime | Fully generated |
| `nginx.conf` | Nginx configuration template copied into the image | Fully generated |
| `scripts/container_start.sh` | Container startup | Fully generated |
| `conf/INSTALL_SETTINGS.md` | Profile/add-on settings reference | Standard-managed |
| `conf/docker_*_settings.txt` | Test and production values | Schema-managed |

See the [React/Vite profile](../profiles/react-vite.md).

### Next.js

| Path | Purpose | Ownership |
| --- | --- | --- |
| `Dockerfile` | Next.js build and runtime image | Fully generated |
| `scripts/container_start.sh` | Container startup | Fully generated |
| `src/pages/health.tsx` | Pages-router health endpoint | Fully generated |
| `conf/INSTALL_SETTINGS.md` | Profile/add-on settings reference | Standard-managed |
| `conf/docker_*_settings.txt` | Test and production values | Schema-managed |

Next.js does not generate `nginx.conf` or `install.sh`. See the [Next.js profile](../profiles/nextjs.md).

## 4. Add-on-generated files

Add-on Compose, installer, and documentation fragments are compiled into common outputs rather than emitted as fragment directories.

| Add-on | Generated paths | Ownership |
| --- | --- | --- |
| Apache | `conf/apache/apache_{test,production}_settings.txt`; `conf/apache/{00-logs,01-reverse-proxy,02-server-status}.conf` | Settings are schema-managed; configuration is standard-managed except `additional-apache-routes` in the proxy file |
| Keycloak | `conf/keycloak/keycloak_{test,production}_settings.txt`; `conf/keycloak/realm-{test,production}.json` | Settings are schema-managed; realm JSON has standard-required keys and application-maintained values |
| Nextstrain | `conf/nextstrain/nextstrain_{test,production}_settings.txt`; `nextstrain/Dockerfile`; `nextstrain/auspice-config.json` | Settings are schema-managed; Dockerfile is generated; JSON has standard-required keys and application-maintained values |
| Samba | `conf/samba/samba_{test,production}_settings.txt` | Schema-managed; its generated service is test-only |

Schema-managed settings preserve values and application-only variables while synchronization adds missing standard names. The listed JSON files preserve scalar values while enforcing required object structure.

See [Add-ons](../addons/README.md), [Apache](../addons/apache.md), and [Keycloak](../addons/keycloak.md). Nextstrain and Samba add topology-specific material to generated documentation.

## 5. Shared deployment library

The scaffold vendors the canonical library into:

```text
deployment/lib/container/
  common.sh
  check_config.sh
  django.sh
```

Do not edit files under `deployment/lib/` in an application repository. Change reusable behavior centrally, then use:

```bash
python3 /path/to/buisciii-deployment-standards/scripts/scaffold.py \
  check-lib /path/to/application

python3 /path/to/buisciii-deployment-standards/scripts/scaffold.py \
  sync-lib /path/to/application
```

## 6. Scaffold state

`.bu-isciii-deployment/state.json` records the normalized scaffold configuration, standards source/version, and generated-artifact hashes. `check` and `sync` use it to distinguish central updates from local changes and retain the initialized topology.

Commit this file with the baseline. Do not edit it manually. See the [project descriptor](project-descriptor.md) for topology inputs.

## 7. Ownership summary

| Class | Allowed change | Examples |
| --- | --- | --- |
| Fully generated / standard-managed | Change the descriptor or owning central template, not the generated file | Compose, Dockerfile, smoke test, startup scripts, health files, ignore files |
| Standard-managed with application blocks | Edit only inside matching markers | README, LEAME, installers, Django URLs, Apache routes |
| Schema-managed configuration | Maintain values and application-only entries; retain required names or JSON structure | Settings files, realm JSON, Auspice JSON |
| Application-owned with contract checks | Customize within its documented structure | Django `conf/template_settings.py` |
| Shared library copy | Never edit locally | `deployment/lib/**` |
| Scaffold metadata | Commit; do not edit manually | `.bu-isciii-deployment/state.json` |

Deployment-time files are outside this source-tree map: protected copies under `deployment/settings/`, `.env.test.file`, `.env.production.file`, rendered `deployment/apache/` files, containers, named volumes, bind data, logs, and other persistent state. See [Configuration](../guides/configuration.md) and the generated runbook.
