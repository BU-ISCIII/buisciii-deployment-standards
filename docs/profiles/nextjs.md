# Next.js deployment profile

## Overview

Selecting the nextjs profile builds a Next.js application and runs it with a persistent, unprivileged Node server. Unlike React/Vite, it is not reduced to a static Nginx bundle: server rendering, middleware, route handlers, proxy routes, and authentication can execute at runtime.

The profile has no install.sh, migration phase, fixture loading, or runtime bootstrap callback.

## Generated artifacts

| Path | Purpose | Ownership |
|---|---|---|
| Dockerfile | Dependency, build, and production Node image stages. | Profile-managed |
| scripts/container_start.sh | Validates the Next.js build and starts the Node server. | Profile-managed |
| src/pages/health.tsx | Minimal HTTP health page used by orchestration. | Profile-managed baseline |
| conf/docker_test_settings.txt | Disposable test build/runtime settings. | Generated template |
| conf/docker_production_settings.txt | Production template copied to a protected file. | Generated template |
| conf/INSTALL_SETTINGS.md | Next.js phase and sensitivity matrix. | Profile-managed |

The common scaffold generates container_install.sh, Compose, and smoke_test.sh with Next.js-owned fragments. See the [generated project structure](../reference/generated-project-structure.md).

## Build model

The Dockerfile has three stages:

1. deps uses node:22-bookworm-slim, copies package manifests, and runs npm ci;
2. build copies the application, exposes the supported build variables, runs npm run build, and writes .next/.deployed_revision; and
3. prod copies package manifests, node_modules, .next, public, and the startup script into a Node runtime image.

The implementation does not use Next.js standalone output and does not execute node server.js. It retains node_modules and runs the package start script. The production image uses NODE_ENV=production and runs as node:node.

Production builds are invoked directly by the selected engine with only the supported NEXT_PUBLIC_* arguments and GIT_REVISION. Test builds use the same Dockerfile through Compose.

## Configuration model

### Browser-visible build values

The current build accepts:

- NEXT_PUBLIC_API_BASE_URL;
- NEXT_PUBLIC_SECOND_API_BASE_URL;
- NEXT_PUBLIC_KEYCLOAK_URL;
- NEXT_PUBLIC_KEYCLOAK_REALM;
- NEXT_PUBLIC_KEYCLOAK_CLIENT_ID;
- NEXT_PUBLIC_USE_CASE_DATA_MODE; and
- NEXT_PUBLIC_USE_CASE_ALERTS_CONTACT_EMAIL.

These values are available while npm run build runs and are embedded where referenced by client-side code. They are visible to users and MUST NOT contain secrets. Changing them requires an image rebuild.

Browser API and Keycloak URLs must be reachable from the user's browser. Compose service names are internal DNS names and are not suitable browser URLs unless an external routing layer deliberately exposes the same name. Same-origin paths such as /api/v1 can let the Next.js server proxy browser requests to internal services.

### Server runtime values

Compose injects AUTH_SECRET, AUTH_URL, AUTH_TRUST_HOST, NEXTAUTH_URL, PATHOCORE_API_PROXY_TARGET, and MEPRAM_OMOP_API_PROXY_TARGET when the container starts.

AUTH_SECRET is sensitive server configuration. The Dockerfile defines only build-only-placeholder during next build so applications that initialize authentication at build time can compile without embedding the real runtime secret. The production secret is supplied only to the running container.

AUTH_URL and NEXTAUTH_URL are public application/callback origins used by server-side authentication behavior. The proxy targets are internal Compose-network URLs used by server routes; they are not browser URLs and are checked against deployment wiring by the outer installer.

APP_PORT and HOSTNAME configure the Node listener. The image defaults are 3000 and 0.0.0.0.

See [configuration variables](../reference/configuration-variables.md) and the [configuration guide](../guides/configuration.md).

## Runtime process

container_start.sh requires /app/.next/BUILD_ID and fails if the build artifact is missing. It then executes:

    npm run start -- --hostname HOSTNAME --port APP_PORT

The npm/Next.js process becomes PID 1. The generated image and Compose service run as the non-root Node identity, UID/GID 1000 by default.

There is no runtime bootstrap. The profile bootstrap and running-permission callbacks are no-ops.

## Ports and networking

APP_PORT defaults to 3000. The server listens on 0.0.0.0 inside the container. Production publishes the host port on 127.0.0.1; test publishes it on 0.0.0.0.

Network scopes are distinct:

| Scope | Address form |
|---|---|
| Compose server-to-server | Service DNS name and internal APP_PORT |
| Deployment-host check | 127.0.0.1 and the published APP_PORT |
| Browser/public callback | Public origin or same-origin browser path |

## Persistence

The application is stateless by default. The image contains the built application. The root filesystem is read-only, while /tmp and /app/.next/cache are writable tmpfs mounts.

The cache is ephemeral and is lost when the container is replaced. No named volume or host bind is generated for uploads, cache, or other application data. Applications that require persistence need an explicitly owned topology change rather than edits to the generated lifecycle.

## Health, readiness, and smoke checks

| Mechanism | Next.js behavior |
|---|---|
| Health page | src/pages/health.tsx returns ok. |
| Image/Compose healthcheck | Node requests http://127.0.0.1:APP_PORT/health/ and requires a 2xx/3xx response. |
| Installer readiness | Requires the container to run and /app/.next/BUILD_ID to exist. |
| Profile smoke check | Requires a running container and the same BUILD_ID artifact. |
| Common smoke check | Requests /health/ through the host-loopback published port. |

These checks prove that the build artifact exists and the health page responds. They do not verify server rendering, proxy targets, authentication callbacks, Keycloak login, API responses, or application workflows. See the [smoke-test reference](../reference/scripts/smoke-test.md).

## Test and production

| Area | Test | Production |
|---|---|---|
| Build/runtime architecture | Multi-stage build and Node server | Same |
| Configuration source | Disposable test settings | Protected settings copied from the production template |
| NEXT_PUBLIC_* | Test values embedded during build | Production values embedded during build |
| Server-only configuration | Test runtime values | Protected runtime values |
| Published port | All host interfaces | Host loopback |
| Cache | Ephemeral tmpfs | Ephemeral tmpfs |
| Bootstrap/persistence | None | None by default |

## Application customization

Application maintainers own the Next.js source, package manifests and scripts, pages/routes, server handlers, authentication integration, proxy implementation, and the meaning of use-case variables. They must keep browser-visible and server-only configuration separate.

Adding a NEXT_PUBLIC_* variable requires installation-setting documentation and explicit build-argument/profile support. Adding server-only runtime configuration requires corresponding settings and Compose environment wiring. Merely defining a value in a file does not make it available in the correct phase.

Do not edit generated lifecycle callbacks or vendored shared libraries locally. Reusable changes to the image model, supported build/runtime variables, health page, readiness, or smoke checks belong under scaffold/templates/profiles/nextjs/.

## Optional integrations

[Apache](../addons/apache.md) may reverse-proxy the Node service. [Keycloak](../addons/keycloak.md) may provide the public OIDC realm/client represented by NEXT_PUBLIC_KEYCLOAK_* values. The application still owns its Auth.js/OIDC and proxy-route implementation; selecting an addon does not add those workflows automatically.

## Difference from React/Vite

React/Vite serves immutable browser files from Nginx and compiles its frontend-specific application configuration at build time. Next.js keeps a Node server, combines browser-visible build values with server-only runtime values, and provides ephemeral writable cache space. Neither profile performs runtime bootstrap.

## Further reading

- [Next.js environment variables](https://nextjs.org/docs/pages/guides/environment-variables)
- [Next.js self-hosting](https://nextjs.org/docs/pages/guides/self-hosting)
