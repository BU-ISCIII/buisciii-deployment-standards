# Docker Compose

Compose describes the containers that form one deployment and how they connect. In this repository, generated Compose files are an input to the standard installer, not a replacement for it.

A **service** is one runnable component, such as an application or database. A **network** lets services communicate. A **named volume** stores data managed by the container engine, while a **bind mount** exposes a specific host path. A port mapping makes a container port reachable on the host.

```yaml
services:
  web:
    # Application container
  web-db:
    # Supporting database container
```

For more background, see the official [Docker Compose application model](https://docs.docker.com/compose/intro/compose-application-model/).

## Generated Compose files

The scaffold generates two complete models:

- `docker-compose.test.yml` for the test deployment;
- `docker-compose.prod.yml` for the production deployment.

Each model is assembled rather than copied from one large template:

```text
common services/network structure
              +
selected profile fragments
              +
selected addon fragments
              |
              v
 docker-compose.test.yml
 docker-compose.prod.yml
```

The common template creates the document structure and the `deployment_net` network. `scripts/scaffold.py` renders one service fragment for every application, adds profile support services, adds selected addon services, and collects their named volumes.

The generated Compose files are standard-managed. Change the project descriptor, the owning template, or an existing extension point instead of patching generated YAML in an application repository. Direct changes are reported as managed drift by `scripts/scaffold.py check`.

## Services, profiles and addons

Every declared application becomes a Compose service. The selected profile owns its framework-specific build, environment, mounts, health check, and runtime behavior:

- [Django](../profiles/django.md);
- [Next.js](../profiles/nextjs.md);
- [React/Vite](../profiles/react-vite.md).

A Django profile also adds a test MySQL service. Production uses either an external database or a generated MySQL service according to the descriptor `DATABASE` option.

Selected addons can add supporting services:

- [Apache](../addons/apache.md) adds a reverse-proxy service;
- [Keycloak](../addons/keycloak.md) adds Keycloak and its MySQL database;
- Nextstrain adds a visualization service;
- Samba adds a test-only file service.

A multi-service or orchestrator descriptor places all selected application and addon services in the same generated model. Stable service names matter because Compose also uses them as internal DNS names.

## Networks

Every generated service joins the single `deployment_net` network. Services on this network can reach each other by service name or an explicit network alias, such as the `keycloak` alias.

Internal communication does not require publishing every service port on the host. For example, generated MySQL support services use port `3306` inside the network; the production variants are not published publicly. The standard does not generate additional network-isolation layers.

## Ports

A container port is used inside `deployment_net`. A published port maps a host address and port to that container port.

For example, a production Django service uses a mapping equivalent to:

```yaml
ports:
  - "127.0.0.1:8001:8001"
```

The actual value comes from installation settings. Binding to `127.0.0.1` keeps the application reachable from the host or a host reverse proxy without listening on every host interface.

Port policy varies by component and mode:

- production Django, Next.js, Keycloak, and Nextstrain services bind their published application ports to loopback;
- React/Vite binds to loopback in both generated modes;
- test Django and Next.js application ports bind to `0.0.0.0`;
- Apache uses the configured `APACHE_BIND_HOST` and can be the public entry point.

External TLS, firewall rules, and host networking belong to the deployment infrastructure, not this guide.

## Volumes and bind mounts

Profiles and addons declare storage according to what they own.

Named volumes currently cover data such as Django documents and static files, optional Compose-managed Django databases, Keycloak database state, Nextstrain data, and disposable test data. Named volumes survive container recreation until explicitly removed.

Bind mounts currently provide Django production logs and rendered settings, rendered Apache configuration and logs, Keycloak realm import files, and host timezone files where selected templates require them.

A bind source must exist with suitable ownership and mode before the container uses it. Rootless Podman may map container IDs through a user namespace, and the templates use SELinux relabel options where implemented. The installer prepares declared sources and permissions. See [container installer customization](container-install-customization.md) for application-owned path handling.

## Configuration passed to services

Before Compose validation, `container_install.sh` reads the selected installation settings and generates `.env.test.file` or `.env.production.file` with mode `0600`. Compose uses that file for interpolation.

Expressions such as:

```yaml
APP_PORT: ${EXAMPLE_APP_APP_PORT:?EXAMPLE_APP_APP_PORT is required}
```

make Compose fail when a required deployment value is missing. The generated model then routes values according to the owning profile:

- `environment` entries configure running containers;
- `build.args` supply public or non-sensitive image-build inputs where a profile requires them;
- named volumes and bind mounts supply persistent data or rendered files;
- Django production settings use the separate build-secret and runtime rendering flow implemented by the installer.

The repository does not use Compose secret objects as a universal configuration mechanism. See [Configuration](configuration.md) for the full settings flow.

## Dependencies and readiness

`depends_on` expresses startup dependencies where a fragment defines them. Django test waits for its MySQL health check, a production Django service with a Compose-managed database does the same, and Keycloak waits for its database. Apache declares dependencies on the services it proxies.

Startup order is not the same as application readiness. Profile and addon fragments define container health checks, but `container_install.sh` also waits for each application readiness file before preparing running mounts and running bootstrap. Deployment acceptance finishes with the generated smoke test. Do not treat `depends_on` alone as proof that an application is ready.

## Test and production

Differences are owned by each profile or addon rather than imposed as one universal topology.

| Area | Test | Production |
|---|---|---|
| Configuration | Generated test settings | Protected production settings and rejected active `CHANGE_ME` values |
| Django database | Disposable Compose MySQL | External by default, or persistent Compose MySQL when selected |
| Published ports | May bind application services to all host interfaces | Application services generally bind to loopback; Apache remains configurable |
| Storage | Test-specific or disposable volumes where implemented | Declared persistent volumes, bind mounts, or external services |
| Data loading | Implemented test/demo loading may be enabled by the installer | No implicit test data; explicit production demo import is separately controlled |
| Django settings | Rendered into the test image | Rendered on the host and bind-mounted; bootstrap receives a temporary protected copy |

Samba is present only in the test model. Other addons define their own test/production differences, such as disposable Apache test logs or stricter Keycloak production settings.

## Docker and Podman compatibility

The generated model is intended for both Docker and Podman, but the tools are not assumed to behave identically.

The shared installer selects `docker compose` for Docker. For Podman it uses `podman-compose` when available, otherwise `podman compose`. Docker builds explicitly enable BuildKit for Django build-secret mounts.

Generated Django production services add the `host.docker.internal:host-gateway` mapping for host-based dependencies. Rootless Podman can also require user-namespace-aware ownership handling for bind mounts; Docker follows its separate permission fallback. Docker is not required to run rootless.

SELinux labeling and host permission behavior depend on the selected engine and host. The Compose templates include only the relabel options and mounts implemented by this standard.

## Validation

The standard path is to use the installer, for example:

```bash
bash container_install.sh --test --action install --engine docker
```

The installer selects the settings files, creates the protected Compose environment, renders required host files, prepares declared host paths, and then runs Compose `config` before building or starting services. A validation failure stops the lifecycle before those deployment changes.

For direct inspection, use the same generated environment file:

```bash
docker compose --env-file .env.test.file \
  -f docker-compose.test.yml config
```

That file is normally created by `container_install.sh`; running Compose without it can fail required-variable interpolation. With Podman, use the frontend selected by the installer rather than assuming one Podman Compose implementation is installed.

## When to change Compose behavior

Place a change with the component that owns it:

- change `scaffold/templates/common/docker-compose.yml.tmpl` only for document structure shared by all generated deployments;
- change `scaffold/templates/profiles/<profile>/compose/` for framework-specific service, support-service, volume, or environment behavior;
- change `scaffold/templates/addons/<addon>/compose/` for addon services, mounts, volumes, and integration fragments;
- use descriptor options such as service build settings or implemented addon options when the behavior is already configurable.

Application-specific Compose logic must be expressed through an application-owned artifact, descriptor option, or existing extension point; do not patch the standard-managed generated files. If no suitable extension exists, add a reusable one to the appropriate profile or addon instead of putting application assumptions into the common compiler.

For the broader procedure, see the [deployment workflow](deployment-workflow.md) and [scaffold workflow](scaffold-workflow.md). Exact installer options belong in the [container installer reference](../reference/scripts/container-install.md); complete variable lists belong in the [configuration variable reference](../reference/configuration-variables.md) and selected profile/addon documentation.
