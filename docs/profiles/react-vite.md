# React/Vite deployment profile

## Overview

Selecting the react-vite profile builds a browser application with Vite and serves the compiled static bundle from an unprivileged Nginx container.

    Node 22 build stage
        ↓
    compiled dist bundle
        ↓
    nginx-unprivileged runtime image

The profile has no application server, runtime bootstrap, migrations, fixture loading, or persistent application data.

## Generated artifacts

| Path | Purpose | Ownership |
|---|---|---|
| Dockerfile | Multi-stage frontend build and Nginx runtime image. | Profile-managed |
| nginx.conf | Nginx server, single-page route fallback, and health endpoint. | Profile-managed |
| scripts/container_start.sh | Validates the bundle and starts Nginx. | Profile-managed |
| conf/docker_test_settings.txt | Disposable test settings. | Generated template |
| conf/docker_production_settings.txt | Production template copied to a protected file. | Generated template |
| conf/INSTALL_SETTINGS.md | React/Vite configuration matrix. | Profile-managed |

The common scaffold also generates container_install.sh, Compose files, and smoke_test.sh with React/Vite-owned fragments. See the [generated project structure](../reference/generated-project-structure.md).

## Image build

The build stage uses node:22-alpine. It copies package.json and package-lock.json, runs npm ci, copies the application, runs npm run build, and records GIT_REVISION in dist/.deployed_revision.

The runtime stage uses nginxinc/nginx-unprivileged:1.27-alpine. It copies nginx.conf as the Nginx template, copies dist to /usr/share/nginx/html, installs the generated startup script, and runs as UID/GID 101:101 by default. The image contains the compiled bundle, not Node build tooling.

Production application builds are issued directly by the selected container engine with GIT_REVISION and VITE_API_BASE_URL. Test builds use the same Dockerfile through Compose.

## Build-time browser configuration

VITE_API_BASE_URL is passed as a Docker build argument and exported while npm run build executes. It is compiled into the browser bundle. Changing it requires rebuilding the image; recreating the container alone does not change the value.

Every VITE_* value consumed by application code is browser-visible and MUST NOT contain passwords, client secrets, private keys, or other secrets. New application-specific VITE_* values require corresponding build arguments, installation-setting entries, and profile implementation support; adding a value only to an environment file does not automatically place it in the build.

VITE_API_BASE_URL must be an address or path usable by the user's browser. A Compose service name is normally valid only inside the Compose network and must not be configured as a browser URL. Use the public API origin or a same-origin path routed by the deployed proxy.

See [configuration variables](../reference/configuration-variables.md) and the [configuration guide](../guides/configuration.md).

## Runtime server

container_start.sh requires /usr/share/nginx/html/index.html and fails if the build artifact is absent. It then executes nginx -g 'daemon off;' so Nginx becomes container PID 1.

Nginx listens on APP_PORT, defaults to index.html, and uses try_files to fall back to /index.html for client-side routes. /health/ returns plain-text ok without evaluating frontend JavaScript or calling an API.

The container filesystem is read-only. Compose provides temporary writable filesystems for /tmp, /var/cache/nginx, and /var/run. These tmpfs mounts disappear when the container is replaced.

There is no runtime bootstrap callback; the generated callback returns successfully without work. There are also no profile running-mount permission operations.

## Ports and networking

APP_PORT defaults to 8080 and is used for the Nginx listener, image/Compose healthchecks, and the host-published port. Both generated test and production Compose services bind the host side to 127.0.0.1.

Inside the Compose network, other services address the frontend by its Compose service name and APP_PORT. From the deployment host, checks use 127.0.0.1:APP_PORT. Browser users require the externally published proxy/DNS URL; none of these scopes is interchangeable automatically.

## Persistence

The profile is stateless. The browser bundle is immutable image content and is recovered by rebuilding the recorded revision. No named volume or host bind is generated for application data. Runtime Nginx cache/run files use ephemeral tmpfs.

## Health, readiness, and smoke checks

| Mechanism | React/Vite behavior |
|---|---|
| Image/Compose healthcheck | wget requests http://127.0.0.1:APP_PORT/health/. |
| Installer readiness | Requires the container to run and /usr/share/nginx/html/index.html to exist. |
| Profile smoke check | Requires a running container and the same index.html artifact. |
| Common smoke check | Requests /health/ through the host-loopback published port. |

These checks verify the bundle exists and Nginx responds. They do not execute the browser application, call VITE_API_BASE_URL, validate client-side routing in a browser, or exercise authentication. See the [smoke-test reference](../reference/scripts/smoke-test.md).

## Test and production

| Area | Test | Production |
|---|---|---|
| Build/runtime architecture | Node build, unprivileged Nginx runtime | Same |
| Configuration source | Disposable test settings | Protected settings copied from the production template |
| VITE_API_BASE_URL | Test browser URL compiled at build | Production browser URL compiled at build |
| Published port | Host loopback | Host loopback |
| Filesystem | Read-only with tmpfs runtime paths | Same |
| Persistence/bootstrap | None | None |

The mode changes the selected settings and Compose file, not the profile startup model.

## Application customization

Application maintainers own the React/Vite source, package manifests, routes, API client behavior, and any additional browser configuration their code consumes. They must document the public exposure and rebuild impact of every added VITE_* value.

Do not edit generated lifecycle callbacks or vendored shared libraries in an application repository. Reusable profile changes—Docker build arguments, Nginx behavior, readiness, health, or smoke checks—belong under scaffold/templates/profiles/react-vite/.

## Optional integrations

[Apache](../addons/apache.md) may proxy the frontend service when selected and configured, but React/Vite contributes no Apache-specific mounts. Identity and API behavior are application concerns unless implemented through a selected addon and matching browser-visible configuration.

## Further reading

- [Vite environment variables and modes](https://vite.dev/guide/env-and-mode)
