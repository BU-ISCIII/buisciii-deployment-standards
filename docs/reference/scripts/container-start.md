# container_start.sh reference

## Purpose

container_start.sh is the profile-owned runtime command copied into an application image. It validates the already-built application and starts its foreground process each time a container starts.

container_start.sh owns repeatable runtime startup. Django install.sh --bootstrap owns deployment-time work such as migrations. Restarting a container does not repeat bootstrap operations.

## Profile implementations

All current application profiles generate scripts/container_start.sh and copy it to /usr/local/bin/container_start.sh. Their Dockerfiles use:

    CMD ["/usr/local/bin/container_start.sh"]

| Profile | Runtime user | Final process |
|---|---|---|
| Django | Configured APP_UID:APP_GID | Development server or Gunicorn |
| Next.js | node:node | npm run start |
| React/Vite | 101:101 | Unprivileged Nginx |

The scripts run without root privileges. Host bind-source ownership and running-mount repair belong to [container_install.sh](container-install.md), not the entrypoint.

## Django startup

### Sequence

1. Resolve defaults and export the application path, project module, and Django settings module.
2. Wait for INSTALL_PATH/manage.py.
3. Wait for INSTALL_PATH/virtualenv/bin/activate.
4. Activate the virtual environment.
5. Create INSTALL_PATH/cron and INSTALL_PATH/tmp.
6. Apply mode 0700 only when each directory is owned by the runtime user.
7. Unless disabled, derive a Supercronic file from Django CRONJOBS and start the scheduler when at least one valid job exists.
8. If APP_MODE is dev, replace the entrypoint with Django runserver.
9. Otherwise select the Gunicorn worker count and replace the entrypoint with Gunicorn.

The two staged-file waits each use APP_START_WAIT_TIMEOUT_SECONDS, defaulting to 100 seconds, and poll every 2 seconds. Timeout prints the missing path, lists its parent directory, and exits.

### Runtime paths

| Path | Use |
|---|---|
| INSTALL_PATH/manage.py | Staged Django entrypoint prerequisite |
| INSTALL_PATH/virtualenv/bin/activate | Staged dependency prerequisite |
| INSTALL_PATH/cron | Generated scheduler file and disabled marker |
| INSTALL_PATH/cron/disabled | Disables scheduler startup when present |
| INSTALL_PATH/tmp | Supercronic log directory |
| INSTALL_PATH/tmp/supercronic.log | Scheduler stdout/stderr |

These paths must be writable when the script creates or updates them. The script skips chmod for paths not owned by the runtime identity; it does not attempt ownership repair or use sudo.

### Scheduler

When cron/disabled exists, scheduled jobs are skipped. Otherwise, if supercronic is installed, the script initializes Django and reads CRONJOBS from the active settings module. Entries with fewer than two fields are ignored. Each valid schedule and dotted Python callable becomes a command using the staged virtualenv. An optional third entry and CRONTAB_COMMAND_SUFFIX are appended as command suffixes.

If the generated file is empty, Supercronic is not started. If the binary is missing, startup continues with scheduling disabled. When started, it runs in the background with output redirected to supercronic.log. The script waits one second and fails if that process has already exited. It does not supervise a later scheduler failure after the web process takes over.

### Development process

APP_MODE=dev selects:

    python INSTALL_PATH/manage.py runserver --noreload 0.0.0.0:APP_PORT

Generated test Compose sets APP_MODE to dev. --noreload prevents Django's reloader from duplicating the scheduler process. This branch is for the test deployment; production Compose sets APP_MODE to prod.

### Production process and workers

Production executes:

    gunicorn PROJECT_MODULE.wsgi:application

It binds 0.0.0.0:APP_PORT and supplies:

- workers from WEB_CONCURRENCY when non-empty;
- otherwise 2 workers for one or two online CPUs, or 4 workers for more;
- GUNICORN_THREADS, default 2;
- GUNICORN_KEEPALIVE, default 5 seconds;
- GUNICORN_TIMEOUT, default 300 seconds;
- /dev/shm as the worker temporary directory;
- access and error logs on standard output/error.

CPU detection tries getconf _NPROCESSORS_ONLN, then nproc, then 1. There is no dynamic worker value above 4.

### Django inputs

The script reads APP_INSTALL_PATH or INSTALL_PATH, APP_MODE, APP_PORT, PROJECT_MODULE, DJANGO_SETTINGS_MODULE, APP_START_WAIT_TIMEOUT_SECONDS, WEB_CONCURRENCY, GUNICORN_THREADS, GUNICORN_KEEPALIVE, and GUNICORN_TIMEOUT. Scheduler behavior additionally reads Django CRONJOBS and CRONTAB_COMMAND_SUFFIX. Defaults are embedded in the generated script.

See [configuration variables](../configuration-variables.md) for operator settings.

## Next.js startup

The Next.js script:

1. requires /app/.next/BUILD_ID;
2. exits with a specific missing-artifact message if absent;
3. otherwise executes:

       npm run start -- --hostname HOSTNAME --port APP_PORT

HOSTNAME defaults to 0.0.0.0 and APP_PORT to 3000. The Dockerfile runs it as the non-root node user. It creates no directories, schedules no jobs, and has no development-server branch.

## React/Vite startup

The React/Vite script:

1. requires /usr/share/nginx/html/index.html;
2. exits with a specific missing-bundle message if absent;
3. otherwise executes:

       nginx -g 'daemon off;'

The immutable Vite bundle was created during the image build. The Dockerfile runs this script as UID/GID 101:101 using the unprivileged Nginx image. APP_PORT defaults to 8080 in the image and is consumed by the Nginx configuration template, not directly by this startup script.

## Readiness and health

These are separate signals:

| Signal | Implemented by | Meaning |
|---|---|---|
| Startup prerequisite | container_start.sh | Required staged artifact exists before launching the process. |
| Installer readiness | container_install.sh | Container is running and the profile readiness file exists. |
| Container healthcheck | Dockerfile/Compose | The profile HTTP /health/ endpoint responds successfully. |
| Smoke test | scripts/smoke_test.sh | Later deployment-level checks pass. |

The installer readiness files are manage.py for Django, .next/BUILD_ID for Next.js, and index.html for React/Vite. They are build artifacts, not markers created by the startup script. Their presence does not prove HTTP health, successful bootstrap, scheduler health, or functional acceptance.

Django and Next.js healthchecks request 127.0.0.1:APP_PORT/health/. React/Vite uses wget against the same path. Dockerfile timing defaults differ by profile, and generated Compose supplies its own healthcheck timing.

## Process and signal behavior

Each script ends by using exec for the foreground web process. That process becomes container PID 1 and receives stop signals directly. For Django, the Supercronic process remains a background child while the web process owns PID 1.

## Responsibility boundary

Runtime startup does not:

- build images or stage application source;
- check out Git revisions or install dependencies;
- run Django checks, migrations, migration hooks, fixtures, or collectstatic;
- load application demo/test data;
- operate Compose or sibling services;
- repair host or mounted-path ownership;
- run smoke tests, backups, restores, or rollback.

Those operations belong to the image build, [install.sh](install.md), [container_install.sh](container-install.md), or operational guides. The separation prevents ordinary container restarts from repeating deployment-time state changes.

## Failure behavior

The Django script uses set -euo pipefail; the POSIX frontend scripts use set -eu. Missing staged artifacts, directory creation errors, scheduler generation/startup errors, invalid runtime values, or failure to exec the main process cause a non-zero container exit. Application-process failure later also ends the container.

The engine exposes the failure through container state and logs. Recovery is limited to the generated Compose restart policy (currently unless-stopped); the entrypoint performs no rollback or custom restart loop.

## Lifecycle relationship

    image build
       |
       v
    install.sh --stage (Django only)
       |
       v
    container starts -> container_start.sh -> application process
       |
       v
    container_install.sh waits for readiness
       |
       v
    install.sh --bootstrap (Django only)
       |
       v
    smoke test

See [install.sh](install.md) for Django staging/bootstrap and [smoke_test.sh](smoke-test.md) for deployment checks.
