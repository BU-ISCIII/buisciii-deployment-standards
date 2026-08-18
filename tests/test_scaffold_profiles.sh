#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$repo_root/lib/container/common.sh"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

compose_env_from_settings() {
    local settings_path="$1" prefix="$2" output_path="$3"
    local -a settings_sources=("$prefix|$settings_path")
    local -a explicit_values=(
        "GIT_REVISION|current"
        "${prefix}_IMAGE|profile-test:local"
    )
    write_compose_environment_file \
        "$output_path" settings_sources explicit_values
}

django_target="$work_dir/django-app"
react_target="$work_dir/react-app"
nextjs_target="$work_dir/nextjs-app"
django_config="$work_dir/django.json"
react_config="$work_dir/react.json"
nextjs_config="$work_dir/nextjs.json"
keycloak_config="$work_dir/keycloak.json"
keycloak_target="$work_dir/keycloak-app"
legacy_config="$work_dir/legacy.json"
legacy_service_config="$work_dir/legacy-service.json"
cp "$repo_root/scaffold/project.json.example" "$django_config"
sed 's/"ADDONS": {}/"ADDONS": {"keycloak": {"CONFIG_SERVICE": "app"}}/' \
    "$django_config" > "$keycloak_config"
sed -e 's/"PROFILE": "django"/"PROFILE": "react-vite"/' \
    -e 's#"TEST_INSTALL_CONF": "conf/docker_test_settings.txt",#"TEST_INSTALL_CONF": "conf/docker_test_settings.txt"#' \
    -e '/"PROJECT_MODULE":/d' \
    "$django_config" > "$react_config"
sed -e 's/"PROFILE": "django"/"PROFILE": "nextjs"/' \
    -e 's#"TEST_INSTALL_CONF": "conf/docker_test_settings.txt",#"TEST_INSTALL_CONF": "conf/docker_test_settings.txt"#' \
    -e '/"PROJECT_MODULE":/d' \
    "$django_config" > "$nextjs_config"
printf '%s\n' '{"PROFILE":"django"}' > "$legacy_config"
printf '%s\n' '{"SERVICES":{"app":{"PROFILE":"django","BUILD_CONTEXT":".","INSTALL_CONF":"conf/prod","TEST_INSTALL_CONF":"conf/test","PROJECT_MODULE":"app","APP_PORT":"8001"}}}' \
    > "$legacy_service_config"

if python3 "$repo_root/scripts/scaffold.py" init "$work_dir/legacy-app" \
    --config "$legacy_config" >/dev/null 2>&1; then
    echo "FAIL: new initialization must require the canonical SERVICES schema" >&2
    exit 1
fi
if python3 "$repo_root/scripts/scaffold.py" init "$work_dir/legacy-service-app" \
    --config "$legacy_service_config" >/dev/null 2>&1; then
    echo "FAIL: legacy runtime values must be rejected in SERVICES" >&2
    exit 1
fi

python3 "$repo_root/scripts/scaffold.py" init "$django_target" \
    --config "$django_config" >/dev/null

# Documentation must enumerate topology-owned protected files and must present
# operator decisions as deployment inputs instead of unfinished review markers.
for document in README.md LEAME.md; do
    grep -Fq 'cp deployment/settings/app_production_settings.txt "$BACKUP_DIR/"' \
        "$django_target/$document"
    grep -Fq 'install -m 0600 "$BACKUP_DIR/app_production_settings.txt" deployment/settings/app_production_settings.txt' \
        "$django_target/$document"
done
grep -Fq '| Revision aprobada | Tag o commit inmutable y aprobacion asociada |' \
    "$django_target/LEAME.md"
grep -Fq 'source deployment/settings/app_production_settings.txt' \
    "$django_target/LEAME.md"
grep -Fq 'HOST_LOG_PATH is required for app' "$django_target/LEAME.md"
grep -Fq '"$HOST_LOG_PATH" "$(dirname "$DJANGO_SETTINGS_PATH")"' \
    "$django_target/LEAME.md"
settings_copy_line="$(grep -n 'install -m 0600 conf/docker_production_settings.txt' \
    "$django_target/LEAME.md" | cut -d: -f1)"
host_source_line="$(grep -n 'source deployment/settings/app_production_settings.txt' \
    "$django_target/LEAME.md" | cut -d: -f1)"
test "$settings_copy_line" -lt "$host_source_line"
settings_heading_line="$(grep -n '^## Configurar los ajustes de produccion$' \
    "$django_target/LEAME.md" | cut -d: -f1)"
host_heading_line="$(grep -n '^## Preparar directorios persistentes del host$' \
    "$django_target/LEAME.md" | cut -d: -f1)"
test "$settings_heading_line" -lt "$host_heading_line"
grep -Fq -- '- `app`: confirmar su endpoint `/health/`' "$django_target/LEAME.md"
! grep -Fq -- '- API de `app`:' "$django_target/LEAME.md"
! grep -Fq '<fichero-ajustes-protegido>' "$django_target/LEAME.md"
! grep -Fq '<REVISAR' "$django_target/LEAME.md"

# Optional API/OIDC settings must not leak into ordinary Django projects.
if grep -Eq 'API_(CORS|THROTTLE|DOCS)|OIDC_' \
    "$django_target/conf/docker_production_settings.txt" \
    "$django_target/docker-compose.prod.yml"; then
    echo "FAIL: optional API/OIDC settings leaked into a plain Django service" >&2
    exit 1
fi
for compose_template in prod.service.yml test.service.yml \
    prod.volumes.yml test.volumes.yml test.support-services.yml; do
    test -f "$repo_root/scaffold/templates/profiles/django/compose/${compose_template}.tmpl"
done
for callback in readiness-path.case container-install-conf.case \
    create-host-bind-sources set-host-bind-permissions \
    running-permissions.case bootstrap.case production-build.case smoke-profile-checks; do
    test -f "$repo_root/scaffold/templates/profiles/django/container_install/${callback}.sh.tmpl"
done
test -f "$django_target/install.sh"
test -f "$django_target/conf/template_settings.py"
grep -Fq '"django_extensions"' "$django_target/conf/template_settings.py"
for health_file in __init__.py views.py urls.py README.md; do
    test -f "$django_target/deployment_health/$health_file"
done
grep -Fq 'path("", health_check, name="deployment-health")' \
    "$django_target/deployment_health/urls.py"
grep -Fq 'path("health/", include("deployment_health.urls"))' \
    "$django_target/deployment_health/README.md"
grep -Fq 'conf/urls.py must include deployment_health.urls for the /health/ endpoint' \
    "$django_target/install.sh"
for setting_example in APPS_NAMES CRONJOBS DATA_UPLOAD_MAX_MEMORY_SIZE \
    SECURE_PROXY_SSL_HEADER CSRF_TRUSTED_ORIGINS CONN_MAX_AGE; do
    grep -Fq "$setting_example" "$django_target/conf/template_settings.py"
done
grep -Fq 'RUN --mount=type=secret,id=install_conf' "$django_target/Dockerfile"
grep -Fq 'tar gcc git rsync wget' "$django_target/Dockerfile"
! grep -Fq 'mariadb-connector-c-devel shadow-utils' "$django_target/Dockerfile"
grep -Fq 'python3.11-devel mariadb-connector-c-devel shadow-utils' \
    "$django_target/install.sh"
grep -Fq 'INSTALL_CONF: "conf/.runtime_install_settings.txt"' \
    "$django_target/docker-compose.prod.yml"
grep -Fq 'INSTALL_CONF: "conf/docker_test_settings.txt"' \
    "$django_target/docker-compose.test.yml"
grep -Fq 'runtime_conf=conf/.runtime_install_settings.txt' \
    "$django_target/container_install.sh"
grep -Fq -- '--tables                          Load initial tables; opt-in on upgrades.' \
    "$django_target/container_install.sh"
grep -Fq '[ "$load_tables" = false ] || args+=(--tables)' \
    "$django_target/container_install.sh"
grep -Fq -- '&& -f "$install_script_dir/conf/first_install_tables.json"' \
    "$django_target/install.sh"
grep -Fq -- '--exclude /static --exclude /cron --exclude /tmp --exclude /virtualenv' \
    "$django_target/install.sh"
grep -Fq 'PYTHONPATH= "$INSTALL_PATH/virtualenv/bin/python" -m django startproject' \
    "$django_target/install.sh"
grep -Fq '            "$PROJECT_MODULE" .' "$django_target/install.sh"
grep -Fq -- '--noreload "0.0.0.0:${APP_PORT}"' \
    "$django_target/scripts/container_start.sh"
grep -Fq "APP_PORT='8001'" "$django_target/conf/docker_production_settings.txt"
grep -Fq "DB_HOST='app_db'" "$django_target/conf/docker_test_settings.txt"
grep -Fq 'DB_HOST: app_db' "$django_target/docker-compose.test.yml"
grep -Fq 'app_db:' "$django_target/docker-compose.test.yml"
grep -Fq "DJANGO_DEBUG='true'" "$django_target/conf/docker_test_settings.txt"
grep -Fq "DJANGO_ALLOWED_HOSTS='*'" "$django_target/conf/docker_test_settings.txt"
grep -Fq '0.0.0.0:${APP_APP_PORT:?APP_APP_PORT is required}:${APP_APP_PORT:?APP_APP_PORT is required}' \
    "$django_target/docker-compose.test.yml"
grep -Fq 'APP_PORT: ${APP_APP_PORT:?APP_APP_PORT is required}' "$django_target/docker-compose.prod.yml"
for setting in REQUIRED_MODULES MIGRATION_MODULES APP_SHELL \
    DB_CONN_MAX_AGE DB_HOST DB_PASSWORD EMAIL_HOST LOG_TYPE LOG_PATH \
    CREATE_INITIAL_SUPERUSER DJANGO_SUPERUSER_USERNAME \
    DJANGO_SUPERUSER_EMAIL DJANGO_SUPERUSER_PASSWORD; do
    grep -Eq "^${setting}=" "$django_target/conf/docker_production_settings.txt"
    grep -Eq "^${setting}=" "$django_target/conf/docker_test_settings.txt"
done
grep -Fq '[[ "$WORKFLOW" == "bootstrap" && "$ACTION" == "install" ]]' \
    "$django_target/install.sh"
for legacy_setting in DB_SERVER_IP DB_PASS EMAIL_HOST_SERVER LOCAL_SERVER_IP DNS_URL; do
    ! grep -Eq "^${legacy_setting}=" "$django_target/conf/docker_production_settings.txt"
    ! grep -Eq "^${legacy_setting}=" "$django_target/conf/docker_test_settings.txt"
done
! grep -Fq -- '--ren_app' "$django_target/install.sh"
for hook in install_application_system_packages prepare_application_directories \
    stage_application_custom_files write_application_runtime_env \
    validate_application_runtime before_django_migrate after_django_migrate \
    set_application_permissions restart_application_server; do
    grep -Fq "${hook}()" "$django_target/install.sh"
done
grep -Fq "GUNICORN_TIMEOUT='300'" "$django_target/conf/docker_production_settings.txt"
grep -Fq "EMAIL_PORT='25'" "$django_target/conf/docker_production_settings.txt"
grep -Fq "EMAIL_USE_TLS='False'" "$django_target/conf/docker_production_settings.txt"
bash -n "$django_target/container_install.sh"
bash -n "$django_target/install.sh"
bash -n "$django_target/scripts/container_start.sh"
test ! -e "$django_target/compose"
test ! -e "$django_target/container_install"
test ! -e "$django_target/documentation"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    django_env="$work_dir/django.compose.env"
    compose_env_from_settings \
        "$django_target/conf/docker_test_settings.txt" APP "$django_env"
    docker compose --env-file "$django_env" \
        -f "$django_target/docker-compose.test.yml" config --quiet
fi

python3 "$repo_root/scripts/scaffold.py" init "$react_target" \
    --config "$react_config" >/dev/null
for compose_template in prod.service.yml test.service.yml; do
    test -f "$repo_root/scaffold/templates/profiles/react-vite/compose/${compose_template}.tmpl"
done
for callback in readiness-path.case running-permissions.case bootstrap.case \
    production-build.case smoke-profile-checks; do
    test -f "$repo_root/scaffold/templates/profiles/react-vite/container_install/${callback}.sh.tmpl"
done
test ! -e "$react_target/install.sh"
test ! -e "$react_target/conf/template_settings.py"
test -f "$react_target/nginx.conf"
grep -Fq 'FROM docker.io/library/node:22-alpine AS build' "$react_target/Dockerfile"
grep -Fq 'FROM docker.io/nginxinc/nginx-unprivileged:1.27-alpine' \
    "$react_target/Dockerfile"
grep -Fq 'COPY nginx.conf /etc/nginx/templates/default.conf.template' \
    "$react_target/Dockerfile"
grep -Fq "APP_PORT='8080'" "$react_target/conf/docker_production_settings.txt"
grep -Fq 'APP_PORT: ${APP_APP_PORT:?APP_APP_PORT is required}' "$react_target/docker-compose.prod.yml"
bash -n "$react_target/container_install.sh"
sh -n "$react_target/scripts/container_start.sh"
bash -n "$react_target/scripts/smoke_test.sh"
test ! -e "$react_target/compose"
test ! -e "$react_target/container_install"
test ! -e "$react_target/documentation"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    react_env="$work_dir/react.compose.env"
    compose_env_from_settings \
        "$react_target/conf/docker_test_settings.txt" APP "$react_env"
    docker compose --env-file "$react_env" \
        -f "$react_target/docker-compose.test.yml" config --quiet
fi

python3 "$repo_root/scripts/scaffold.py" init "$keycloak_target" \
    --config "$keycloak_config" >/dev/null

python3 "$repo_root/scripts/scaffold.py" init "$nextjs_target" \
    --config "$nextjs_config" >/dev/null
for compose_template in prod.service.yml test.service.yml; do
    test -f "$repo_root/scaffold/templates/profiles/nextjs/compose/${compose_template}.tmpl"
done
for callback in readiness-path.case running-permissions.case bootstrap.case \
    production-build.case smoke-profile-checks; do
    test -f "$repo_root/scaffold/templates/profiles/nextjs/container_install/${callback}.sh.tmpl"
done
test ! -e "$nextjs_target/install.sh"
test ! -e "$nextjs_target/nginx.conf"
grep -Fq 'FROM docker.io/library/node:22-bookworm-slim AS deps' \
    "$nextjs_target/Dockerfile"
grep -Fq 'USER node:node' "$nextjs_target/Dockerfile"
grep -Fq 'npm run start -- --hostname' "$nextjs_target/scripts/container_start.sh"
grep -Fq "APP_PORT='3000'" "$nextjs_target/conf/docker_production_settings.txt"
grep -Fq "AUTH_SECRET='CHANGE_ME'" "$nextjs_target/conf/docker_production_settings.txt"
grep -Fq 'PATHOCORE_API_PROXY_TARGET:' "$nextjs_target/docker-compose.prod.yml"
grep -Fq 'MEPRAM_OMOP_API_PROXY_TARGET:' "$nextjs_target/docker-compose.prod.yml"
grep -Fq '/app/.next/cache:size=64m' "$nextjs_target/docker-compose.prod.yml"
grep -Fq -- '--build-arg NEXT_PUBLIC_API_BASE_URL=' "$nextjs_target/container_install.sh"
! grep -Fq -- '--build-arg VITE_API_BASE_URL=' "$nextjs_target/container_install.sh"
bash -n "$nextjs_target/container_install.sh"
sh -n "$nextjs_target/scripts/container_start.sh"
bash -n "$nextjs_target/scripts/smoke_test.sh"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    nextjs_env="$work_dir/nextjs.compose.env"
    compose_env_from_settings \
        "$nextjs_target/conf/docker_test_settings.txt" APP "$nextjs_env"
    docker compose --env-file "$nextjs_env" \
        -f "$nextjs_target/docker-compose.test.yml" config --quiet
fi
for document in README.md LEAME.md; do
    grep -Fq '> "$BACKUP_DIR/keycloak-database.sql"' "$keycloak_target/$document"
    grep -Fq '< "$BACKUP_DIR/keycloak-database.sql"' "$keycloak_target/$document"
    grep -Fq 'up -d keycloak_db' "$keycloak_target/$document"
done

# Outer deployment structure is common regardless of the selected framework.
diff <(grep '^## ' "$django_target/README.md") \
    <(grep '^## ' "$react_target/README.md") >/dev/null
diff <(grep '^## ' "$django_target/LEAME.md") \
    <(grep '^## ' "$react_target/LEAME.md") >/dev/null
diff <(grep '^# [0-9][0-9]*\.' "$django_target/container_install.sh") \
    <(grep '^# [0-9][0-9]*\.' "$react_target/container_install.sh") >/dev/null
cmp "$django_target/.dockerignore" "$react_target/.dockerignore" >/dev/null

if grep -Eq 'healthcheck:|restart: unless-stopped|MYSQL_DATABASE:|read_only: true|tmpfs:' \
    "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: profile Compose YAML must live in profile templates" >&2
    exit 1
fi
if grep -Eq 'APP_(UID|GID|PORT)_VALUE|REPO_PATH_VALUE|INSTALL_PATH_VALUE|USER_JSON|PORT_BIND_JSON|DB_[A-Z_]+_VALUE|DJANGO_[A-Z_]+_VALUE|VITE_API_BASE_URL_VALUE' \
    "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: profile Compose environment expressions must live in templates" >&2
    exit 1
fi
if grep -Eq 'prepare_django_settings_bind_mount|stage_container_runtime_config|python manage.py check|immutable React runtime|no runtime bootstrap' \
    "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: profile installer callbacks must live in profile templates" >&2
    exit 1
fi
if grep -Eq '_DEFAULT_(REPO_PATH|INSTALL_PATH|APP_PORT|APP_UID|APP_GID)|"(8001|1212|101|300|3306|djangopass|test-only-change-me)"' \
    "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: profile runtime defaults must live in profile settings templates" >&2
    exit 1
fi
if grep -Eq 'DJANGO_(TEST_BUILD|CONTAINER)_INSTALL_CONF|_TEST_BUILD_INSTALL_CONF|_CONTAINER_INSTALL_CONF|INSTALL_CONF_PATH' \
    "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: fixed Django lifecycle paths must live in Django templates" >&2
    exit 1
fi
if grep -Eq 'smoke_checks|SMOKE_CHECKS' "$repo_root/scripts/scaffold.py" \
    "$repo_root/scaffold/templates/common/scripts/smoke_test.sh.tmpl"; then
    echo "FAIL: smoke URL iteration must be generic" >&2
    exit 1
fi

test ! -e "$repo_root/scaffold/templates/profiles/django/container_install.sh.tmpl"
test ! -e "$repo_root/scaffold/templates/profiles/react-vite/container_install.sh.tmpl"
test ! -e "$repo_root/scaffold/templates/profiles/nextjs/container_install.sh.tmpl"
test ! -e "$repo_root/scaffold/templates/profiles/django/README.md.tmpl"
test ! -e "$repo_root/scaffold/templates/profiles/react-vite/README.md.tmpl"
test ! -e "$repo_root/scaffold/templates/profiles/nextjs/README.md.tmpl"

grep -Fq 'local deadline=$((SECONDS + 60))' "$django_target/install.sh"
grep -Fq 'after 60 seconds' "$django_target/install.sh"

if python3 "$repo_root/scripts/scaffold.py" sync "$django_target" \
    --config "$react_config" >/dev/null 2>&1; then
    echo "FAIL: sync must reject changing an initialized framework profile" >&2
    exit 1
fi

echo "Scaffold profile generation tests passed."
