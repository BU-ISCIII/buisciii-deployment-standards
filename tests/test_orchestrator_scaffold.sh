#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="$(mktemp -d)"
single_target="$(mktemp -d)"
trap 'rm -rf "$target" "$single_target"' EXIT

python3 "$repo_root/scripts/scaffold.py" init "$target" \
    --config "$repo_root/tests/fixtures/mixed_project.json" >/dev/null

grep -Fq 'def documentation_template_values(' "$repo_root/scripts/scaffold.py"
for fragment in service-inventory-row.md config-map-example.txt no-addons.md; do
    test -f "$repo_root/scaffold/templates/common/documentation/${fragment}.tmpl"
done
for profile in django react-vite; do
    test -f "$repo_root/scaffold/templates/profiles/$profile/documentation/profile.md.tmpl"
    test -f "$repo_root/scaffold/templates/profiles/$profile/documentation/persistence-rows.md.tmpl"
done
for addon in apache keycloak samba; do
    test -f "$repo_root/scaffold/templates/addons/$addon/documentation/addon.md.tmpl"
done
test -f "$repo_root/scaffold/templates/addons/keycloak/documentation/persistence-rows.md.tmpl"
if grep -Eq 'Django services build with|React/Vite services use|Apache generates either|Keycloak provides centralized|browser bundle.*Immutable container' \
    "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: generated documentation content must live in documentation templates" >&2
    exit 1
fi
grep -Fq 'def settings_template_values(' "$repo_root/scripts/scaffold.py"
grep -Fq 'def container_installer_template_values(' "$repo_root/scripts/scaffold.py"
grep -Fq '# PROFILE COMPILERS' "$repo_root/scripts/scaffold.py"
grep -Fq '# GENERIC ADD-ON COMPILER' "$repo_root/scripts/scaffold.py"
grep -Fq '# COMPOSE AND ARTIFACT ASSEMBLY' "$repo_root/scripts/scaffold.py"
if grep -Eq '^def (apache_|compile_apache|compile_keycloak)' "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: add-on behavior must use the generic add-on compiler" >&2
    exit 1
fi
if grep -Fq 'def orchestrator_template_values(' "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: installer rendering must not retain the old orchestration name" >&2
    exit 1
fi
for apache_template in 00-logs.conf 01-reverse-proxy.conf 02-server-status.conf; do
    test -f "$repo_root/scaffold/templates/addons/apache/conf/${apache_template}.tmpl"
done
for addon in apache keycloak; do
    test -f "$repo_root/scaffold/templates/addons/$addon/conf/docker_production_settings.txt.tmpl"
    test -f "$repo_root/scaffold/templates/addons/$addon/conf/docker_test_settings.txt.tmpl"
    test -f "$repo_root/scaffold/templates/addons/$addon/conf/INSTALL_SETTINGS.md.tmpl"
done
for callback in create-host-bind-sources set-host-bind-permissions running-permissions.case; do
    test -f "$repo_root/scaffold/templates/addons/apache/container_install/${callback}.sh.tmpl"
    test -f "$repo_root/scaffold/templates/addons/keycloak/container_install/${callback}.sh.tmpl"
done
for fragment in django-prod-mounts django-test-mounts application-mount \
    prod.service-volumes test.service-volumes test.volumes; do
    test -f "$repo_root/scaffold/templates/addons/apache/compose/${fragment}.yml.tmpl"
done
if grep -Eq 'apache_defaults|keycloak_defaults|LogFormat|ProxyPass|LimitRequestBody' \
    "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: add-on configuration/defaults must live in templates, not scaffold.py" >&2
    exit 1
fi
if grep -Eq 'operational values, not Django settings|Preserve the Keycloak database independently' \
    "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: add-on settings guidance must live in add-on templates" >&2
    exit 1
fi
if grep -ERq '\$\{(APACHE|SERVER_STATUS)_[A-Z0-9_]+:-' \
    "$repo_root/scaffold/templates/addons/apache/compose"; then
    echo "FAIL: Apache Compose defaults must live in Apache settings templates" >&2
    exit 1
fi
if grep -Eq 'apache_(running_mount|host_bind)_permission_spec|mkdir -p.*deployment/apache' \
    "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: Apache installer callbacks must live in add-on templates" >&2
    exit 1
fi
if grep -Eq 'keycloak(_db)?_running_mount_permission_spec|keycloak_host_bind_permission_spec|compgen -G.*keycloak_import_path' \
    "$repo_root/scripts/scaffold.py"; then
    echo "FAIL: Keycloak installer callbacks must live in add-on templates" >&2
    exit 1
fi

prod="$target/docker-compose.prod.yml"
test_compose="$target/docker-compose.test.yml"
grep -Fq '# BEGIN BU-ISCIII SERVICE: api (django)' "$prod"
grep -Fq '# BEGIN BU-ISCIII SERVICE: web (react-vite)' "$prod"
grep -Fq '# BEGIN BU-ISCIII ADDON: apache' "$prod"
grep -Fq '# BEGIN BU-ISCIII ADDON: keycloak' "$prod"
if grep -Fq 'build:' "$prod" && grep -Fq 'secrets:' "$prod"; then
    echo "FAIL: orchestrator Compose must not require build.secrets support" >&2
    exit 1
fi
grep -Fq -- '--secret "id=install_conf,src=' "$target/container_install.sh"
grep -Fq 'KC_DB: mysql' "$prod"
grep -Fq 'keycloak_db_data:/var/lib/mysql' "$prod"
grep -Fq '${KEYCLOAK_IMPORT_PATH:-./keycloak/tmp-import}:/opt/keycloak/data/import:ro,z' "$prod"
grep -Fq 'KEYCLOAK_REALM_SOURCE_PATH' "$target/container_install.sh"
grep -Fq '"$realm_file|1000:0|0640"' "$target/container_install.sh"
grep -Fq 'api_static:' "$prod"
grep -Fq 'api_documents:' "$prod"
grep -Fq 'api_test_db:' "$test_compose"
grep -Fq 'api_static:${API_INSTALL_PATH:?API_INSTALL_PATH is required}/static:ro,z' "$prod"
grep -Fq 'api_documents:${API_INSTALL_PATH:?API_INSTALL_PATH is required}/documents:ro,z' "$prod"
grep -Fq 'host.docker.internal:host-gateway' "$prod"
grep -Fq 'REQUIRED runtime-rendered read-only configuration bind sources' "$prod"
grep -Fq 'OPTIONAL APP MOUNTS belong in ADDONS.apache.MOUNTS' "$prod"
grep -Fq '${APACHE_LOG_PATH:?APACHE_LOG_PATH is required}:/var/log/httpd:z' "$prod"
grep -Fq '"$apache_log_path|1001:0|0775"' "$target/container_install.sh"
grep -Fq 'apache_test_logs:/var/log/httpd:z' "$test_compose"
grep -Fq '  apache_test_logs:' "$test_compose"
if grep -Eq '(API|WEB)_GUNICORN_TIMEOUT:' "$prod"; then
    echo "FAIL: rendered Apache configuration must not require runtime container settings" >&2
    exit 1
fi

test ! -e "$target/deployment/apache/00-logs.conf"
test ! -e "$target/deployment/apache/01-reverse-proxy.conf"
test ! -e "$target/deployment/apache/02-server-status.conf"
test -f "$target/conf/apache/00-logs.conf"
test -f "$target/conf/apache/01-reverse-proxy.conf"
test -f "$target/conf/apache/02-server-status.conf"
diff -u "$repo_root/tests/fixtures/apache_logs_expected.conf" \
    "$target/conf/apache/00-logs.conf"
test -f "$target/Dockerfile"
grep -Fq 'FROM docker.io/library/node:22-alpine AS build' "$target/Dockerfile"
grep -Fq '# Apache reverse proxy source configuration for example-orchestrator.' \
    "$target/conf/apache/01-reverse-proxy.conf"
grep -Fq 'ServerName ${APACHE_SERVER_NAME}' \
    "$target/conf/apache/01-reverse-proxy.conf"
grep -Fq 'ProxyPass / http://${APACHE_UPSTREAM_SERVICE}:${APACHE_UPSTREAM_PORT}/' \
    "$target/conf/apache/01-reverse-proxy.conf"
grep -Fq 'LimitRequestBody ${APACHE_LIMIT_REQUEST_BODY}' \
    "$target/conf/apache/01-reverse-proxy.conf"
grep -Fq '# OPTIONAL SECOND DNS VIRTUAL HOST' \
    "$target/conf/apache/01-reverse-proxy.conf"
grep -Fq 'CustomLog logs/<LOG_STEM>-apache.access.log proxy env=forwarded' \
    "$target/conf/apache/01-reverse-proxy.conf"
grep -Fq 'ServerName ${SERVER_STATUS_SERVER_NAME}' \
    "$target/conf/apache/02-server-status.conf"
grep -Fq 'Allow from ${SERVER_STATUS_ALLOW_FROM}' \
    "$target/conf/apache/02-server-status.conf"
test -f "$target/conf/apache/apache_production_settings.txt"
test -f "$target/conf/keycloak/keycloak_production_settings.txt"
grep -Fq '# Apache add-on' "$target/conf/apache/apache_production_settings.txt"
grep -Fq "APACHE_PORT='8080'" "$target/conf/apache/apache_production_settings.txt"
grep -Fq "APACHE_SERVER_NAME='CHANGE_ME_DNS_NAME'" \
    "$target/conf/apache/apache_production_settings.txt"
grep -Fq "# APACHE_SECOND_SERVER_NAME='CHANGE_ME_SECOND_DNS_NAME'" \
    "$target/conf/apache/apache_production_settings.txt"
grep -Fq "# APACHE_SECOND_LOG_STEM='CHANGE_ME_LOG_STEM'" \
    "$target/conf/apache/apache_production_settings.txt"
grep -Fq "APACHE_CONF_PATH=''" "$target/conf/apache/apache_production_settings.txt"
grep -Fq "SERVER_STATUS_ALLOW_FROM='127.0.0.1 localhost'" \
    "$target/conf/apache/apache_production_settings.txt"
grep -Fq "SERVER_STATUS_SERVER_NAME='localhost'" \
    "$target/conf/apache/apache_production_settings.txt"
grep -Fq '# Keycloak add-on' "$target/conf/keycloak/keycloak_production_settings.txt"
grep -Fq "KEYCLOAK_DB_PASSWORD='CHANGE_ME'" "$target/conf/keycloak/keycloak_production_settings.txt"
grep -Fq "APACHE_PORT='8081'" "$target/conf/apache/apache_test_settings.txt"
grep -Fq "APACHE_BIND_HOST='0.0.0.0'" "$target/conf/apache/apache_test_settings.txt"
grep -Fq "# APACHE_SECOND_SERVER_NAME='second.localhost'" \
    "$target/conf/apache/apache_test_settings.txt"
grep -Fq "KEYCLOAK_DB_PASSWORD='keycloak_password'" "$target/conf/keycloak/keycloak_test_settings.txt"
grep -Fq '### Apache' "$target/conf/INSTALL_SETTINGS.md"
grep -Fq '### Keycloak' "$target/conf/INSTALL_SETTINGS.md"
grep -Fq '`SERVER_STATUS_SERVER_NAME`' "$target/conf/INSTALL_SETTINGS.md"
grep -Fq 'configured_services=(api web apache keycloak)' "$target/container_install.sh"
grep -Fq 'service_environment_value "$1" REPO_PATH' \
    "$target/container_install.sh"
grep -Fq 'service_environment_value "$1" INSTALL_PATH' \
    "$target/container_install.sh"
grep -Fq 'INSTALL_PATH="$(service_install_path "$apache_config_service")"' \
    "$target/container_install.sh"
grep -Fq 'Alias /static/ "${INSTALL_PATH}/static/"' \
    "$target/conf/apache/01-reverse-proxy.conf"
grep -Fq 'Alias /documents/ "${INSTALL_PATH}/documents/"' \
    "$target/conf/apache/01-reverse-proxy.conf"
grep -Fq '"|${install_conf_host_by_service[apache]}"' "$target/container_install.sh"
grep -Fq '"|${install_conf_host_by_service[keycloak]}"' "$target/container_install.sh"
grep -Fq 'render_environment_config_template' "$target/container_install.sh"
grep -Fq 'apache_config_service=web' "$target/container_install.sh"

# Add-ons and profile fragments are assembled into the final files; they are
# not emitted as operator-facing Compose overlays.
test "$(find "$target" -name 'docker-compose*.yml' -type f | wc -l)" -eq 2
bash -n "$target/container_install.sh"
bash -n "$target/scripts/smoke_test.sh"
grep -Fq 'install_services=(api web)' "$target/scripts/smoke_test.sh"
grep -Fq 'for service in "${install_services[@]}"; do' \
    "$target/scripts/smoke_test.sh"
grep -Fq 'port_variable="${prefix}_APP_PORT"' "$target/scripts/smoke_test.sh"
if grep -Eq 'check_url (api|web) ' "$target/scripts/smoke_test.sh"; then
    echo "FAIL: smoke URLs must not be generated per service" >&2
    exit 1
fi

# Each individual profile is Compose-validated with its rendered settings in
# test_scaffold_profiles.sh. This mixed fixture intentionally points at a
# sibling API repository that is not created by this test.

python3 "$repo_root/scripts/scaffold.py" sync "$target" >/dev/null
test ! -e "$prod.bu-isciii-update"

# A standalone application selects its only settings file for Apache without
# requiring CONFIG_SERVICE or separate add-on configuration files.
python3 "$repo_root/scripts/scaffold.py" init "$single_target" \
    --config "$repo_root/tests/fixtures/single_django_apache.json" >/dev/null
grep -Fq 'configured_services=(app apache samba)' "$single_target/container_install.sh"
grep -Fq '"|${install_conf_host_by_service[apache]}"' "$single_target/container_install.sh"
grep -Fq '# Apache add-on' "$single_target/conf/apache/apache_production_settings.txt"
grep -Fq "REPO_PATH='/srv/example-django'" "$single_target/conf/docker_production_settings.txt"
grep -Fq "INSTALL_PATH='/opt/example-django'" "$single_target/conf/docker_production_settings.txt"
test -f "$single_target/conf/apache/apache_production_settings.txt"
test -f "$single_target/conf/apache/apache_test_settings.txt"
grep -Fq 'app_test_static:${APP_INSTALL_PATH:?APP_INSTALL_PATH is required}/static:ro,z' \
    "$single_target/docker-compose.test.yml"
grep -Fq 'app_test_documents:${APP_INSTALL_PATH:?APP_INSTALL_PATH is required}/documents:ro,z' \
    "$single_target/docker-compose.test.yml"
grep -Fq 'image: docker.io/dperson/samba:latest' \
    "$single_target/docker-compose.test.yml"
grep -Fq 'samba_test_data:/mnt:z' "$single_target/docker-compose.test.yml"
! grep -Fq 'image: docker.io/dperson/samba:latest' \
    "$single_target/docker-compose.prod.yml"
grep -Fq "SAMBA_USER='samba_user'" \
    "$single_target/conf/samba/samba_test_settings.txt"

echo "Mixed-profile orchestrator scaffold tests passed."
