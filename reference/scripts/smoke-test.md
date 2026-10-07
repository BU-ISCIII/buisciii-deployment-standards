# smoke_test.sh reference

## Purpose

scripts/smoke_test.sh is the generated final acceptance step run by container_install.sh after startup, permission preparation, profile bootstrap, and optional data loading.

Readiness and smoke testing are different. Readiness permits the deployment lifecycle to continue. The smoke test performs the final generated checks. A successful smoke test does not prove every application-specific user workflow works.

## Invocation and options

The outer installer invokes the script as:

    bash scripts/smoke_test.sh --engine ENGINE --compose_file COMPOSE_FILE --env_file GENERATED_ENV

It also supplies --test in test mode.

| Option | Required | Default | Purpose |
|---|---:|---|---|
| --engine docker\|podman | No | docker | Select the engine and Compose frontend. |
| --compose_file PATH | No | docker-compose.prod.yml, or docker-compose.test.yml with --test | Select the Compose model. |
| --env_file PATH | No | none | Source generated values and pass the file to Compose in production. |
| --test | No | production mode | Select test defaults and invocation mode. |
| --help | No | — | Print brief usage and exit successfully. |

Unknown options fail. Options that require values do not have separate friendly missing-value validation; strict shell behavior terminates malformed calls.

The script sources deployment/lib/container/common.sh and uses the same engine selection as the installer: Docker uses docker compose; Podman prefers podman-compose and falls back to podman compose.

## Execution order

1. Parse options and choose the default Compose file.
2. Select and validate the requested container engine/Compose frontend.
3. If --env_file is non-empty, source it with automatic export enabled.
4. Run Compose config for the selected model.
5. Run generated profile checks for each application service.
6. For each application service, resolve its normalized service prefix, require PREFIX_APP_PORT, and request its host-loopback health URL.
7. Print the deployment success message.

Profile fragments are compiled into step 5 in application-service declaration order. No addon-specific fragment is currently generated.

## Checks

### Common checks

| Check | What it proves | What it does not prove |
|---|---|---|
| Compose config succeeds | The selected Compose model interpolates and validates through the selected frontend. | That services started or are healthy. |
| Profile container resolves | A container can be associated with each application service. | That every addon exists. |
| Profile container is running | The application container is running at check time. | Docker/Podman health status or functional correctness. |
| PREFIX_APP_PORT exists | The generated environment provides the application's published port. | That the port is externally reachable. |
| HTTP GET to http://127.0.0.1:PORT/health/ | The application health route returns a curl-success HTTP response from the deployment host within 20 seconds. | Public DNS, external firewall, proxy, TLS, login, or broader workflows. |

curl uses --fail, --silent, --show-error, --location, a 20-second maximum, and discards the response body. Redirects are followed. HTTP 400 or higher fails. The check addresses each application directly through its published host port; it does not route through Apache or another addon.

The common script does not inspect the container health-state field, published port metadata, service logs, or addon container state.

### Django

For each Django service, the generated fragment:

1. resolves the service container;
2. requires it to be running;
3. enters INSTALL_PATH and activates the staged virtual environment;
4. runs python manage.py check;
5. runs showmigrations --plan and rejects output containing [ ];
6. prints a profile pass message.

This verifies Django's standard check framework and rejects a reported unapplied migration. Because the implementation negates the showmigrations-and-grep pipeline, a failing showmigrations command can be masked; success does not independently prove that command completed. It does not rerun migrate, use check --deploy, load fixtures, collect static files, or exercise an application query/workflow.

### Next.js

The fragment requires the service container to be running and checks that /app/.next/BUILD_ID exists. The later common loopback request verifies the /health/ route responds.

### React/Vite

The fragment requires the service container to be running and checks that /usr/share/nginx/html/index.html exists. The later common loopback request verifies the Nginx /health/ route responds.

### Addons

Apache, Keycloak, Nextstrain, and Samba currently contribute no generated smoke checks. Their containers, proxy paths, realm endpoints, shares, and health states are therefore not directly accepted by this script.

## Test and production behavior

The check sequence is identical in both modes. --test changes the default Compose filename and tells the shared Compose helper not to inject the production env file automatically. The explicitly supplied generated env file is still sourced so host HTTP checks use the rendered service ports.

Different Compose models may publish different host addresses or provide different topology, but all application HTTP checks still target 127.0.0.1:APP_PORT. No test credentials, fixtures, or test-only database checks are used by the smoke script.

## Configuration and network scope

The generated environment file supplies service-prefixed APP_PORT values. The service name is uppercased and hyphens become underscores. Other sourced values are available to subprocesses but the common smoke logic does not read them directly.

Compose commands run from the host with the selected Compose model. Profile checks run inside each application container through docker/podman exec. HTTP checks run from the deployment host against loopback. Consequently, a pass does not prove access through an external hostname, load balancer, firewall, TLS terminator, or remote client.

See [configuration variables](../configuration-variables.md) for the generated environment model.

## Health, readiness, smoke, and functional testing

| Mechanism | Current purpose |
|---|---|
| Container healthcheck | Repeatedly probes the profile's local HTTP health route for engine/Compose health state. |
| Installer readiness | Requires the application container to run and its profile build artifact to exist before permissions/bootstrap. |
| Generated smoke test | Validates Compose, profile-specific state, and host-loopback health after deployment stages finish. |
| Application functional test | Exercises real user or integration workflows; not supplied by this generic script. |

These mechanisms are complementary. The smoke script does not query the engine's health status even though profile Compose/Dockerfile definitions provide healthchecks.

## Exit and diagnostics

The script uses set -euo pipefail and stops at the first unhandled failure. Success exits zero after printing the application deployment success message. Failures are non-zero.

Common HTTP failures print the service and URL. Missing APP_PORT uses a FAIL message. The shared running-state helper prints a missing/stopped-container diagnostic and the last 200 log lines for a stopped container. Other failures, including Compose config, profile commands, artifact tests, environment sourcing, and engine selection, emit their command/helper diagnostics.

The smoke script does not print a full Compose status summary and does not automatically stop or roll back services. When called by container_install.sh, its failure makes the overall deployment command fail, potentially leaving the newly recreated services running.

## What success proves

A successful generated smoke test proves, at the time and from the contexts tested, that:

- the selected Compose model validated;
- every application service resolved to a running container;
- each selected profile's generated artifact/check passed;
- Django services produced no detected unapplied-migration marker (subject to the showmigrations pipeline limitation above);
- every application /health/ endpoint responded successfully through its loopback-published host port.

It does not accept addon behavior or application-specific workflows. It does not validate external DNS/TLS, proxy routing, authentication, email, scheduled jobs, background processing, backups, or restore. Application CI and operational acceptance may require separate tests.

## Extension ownership

There is no marked application-owned block or application callback in the generated smoke script.

| Check type | Owner |
|---|---|
| Reusable for every deployment | Common smoke template/shared library |
| Django, Next.js, or React/Vite behavior | Corresponding profile fragment |
| Apache, Keycloak, Nextstrain, or Samba behavior | Corresponding addon fragment, if introduced |
| Application-specific workflow | Separate application validation, unless a supported generic extension point is added |

Do not edit managed generated code or remove a failing contract check in one application. Fix the deployment or the owning common/profile/addon implementation.

## Examples

Production rerun:

    bash scripts/smoke_test.sh --engine docker --compose_file docker-compose.prod.yml --env_file .env.production.file

Test rerun:

    bash scripts/smoke_test.sh --test --engine docker --compose_file docker-compose.test.yml --env_file .env.test.file

The generated env file is not cleaned up by container_install.sh, so the check can be rerun while that protected file and the selected Compose deployment remain available.

See [container_install.sh](container-install.md) for the full lifecycle, [container_start.sh](container-start.md) for runtime startup, and [install.sh](install.md) for Django bootstrap.
