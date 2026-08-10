#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
template="$repo_root/scaffold/templates/common/container_install.sh.tmpl"
target="$(mktemp -d)"
trap 'rm -rf "$target"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
require_text() {
    local pattern="$1" file="$2" description="$3"
    grep -Fq -- "$pattern" "$file" || fail "$description"
}

require_text 'GENERATED SERVICE/ADD-ON CUSTOMIZATION' "$template" \
    "common installer must mark generated customization"
require_text 'install_services={{INSTALL_SERVICES_LITERAL}}' "$template" \
    "common installer must receive normalized application services"
require_text 'permission_services={{PERMISSION_SERVICES_LITERAL}}' "$template" \
    "common installer must receive application/add-on permission services"
require_text 'configured_services={{CONFIGURED_SERVICES_LITERAL}}' "$template" \
    "common installer must receive configuration-owning components"
require_text 'prefix="${1^^}"' "$template" \
    "service environment prefixes must be derived generically"
require_text 'printf '\''%s\n'\'' "${prefix//-/_}"' "$template" \
    "hyphenated service names must map to valid environment prefixes"
require_text 'service_environment_value "$1" REPO_PATH' "$template" \
    "repository paths must use the generic settings lookup"
require_text 'service_environment_value "$1" INSTALL_PATH' "$template" \
    "installation paths must use the generic settings lookup"
require_text 'service_environment_value "$1" APP_UID' "$template" \
    "runtime UIDs must use the generic settings lookup"
require_text 'service_environment_value "$1" APP_GID' "$template" \
    "runtime GIDs must use the generic settings lookup"
require_text 'write_compose_environment_file' "$template" \
    "common installer must generate the prefixed Compose environment"
require_text 'resolve_service_container "$1"' "$template" \
    "container lookup must use the Podman-compatible shared resolver"
if grep -Fq 'ps -q "$1"' "$template"; then
    fail "container lookup must not pass a service to podman-compose ps"
fi
require_text 'prepare_host_bind_source_permissions()' "$template" \
    "common installer must expose host permission policy"
require_text 'prepare_running_container_mount_permissions()' "$template" \
    "common installer must expose running-mount permission policy"
require_text '--secret "id=install_conf,src=' "$template" \
    "common installer must build Django with an ephemeral secret"
require_text 'VITE_API_BASE_URL="$vite_api_url"' "$template" \
    "common installer must build React with public Vite configuration"
require_text 'up -d --force-recreate' "$template" \
    "a successful build must replace containers that reference the old image"

if grep -Eq '\{\{(ENV_PREFIX|REPO_PATH|INSTALL_PATH|UID|GID)_CASES\}\}' "$template"; then
    fail "generic settings lookups must not use generated service case tables"
fi

python3 "$repo_root/scripts/scaffold.py" init "$target" \
    --config "$repo_root/tests/fixtures/mixed_project.json" >/dev/null
generated="$target/container_install.sh"
bash -n "$generated"
require_text 'install_services=(api web)' "$generated" \
    "mixed installer must preserve application order"
require_text 'permission_services=(api web apache keycloak_db keycloak)' "$generated" \
    "mixed installer must include add-ons in permission repair"
require_text 'configured_services=(api web)' "$generated" \
    "add-ons must reuse an application configuration instead of adding files"
require_text 'api) echo django' "$generated" \
    "mixed installer must dispatch the Django profile"
require_text 'web) echo react-vite' "$generated" \
    "mixed installer must dispatch the React profile"
require_text 'stage_container_runtime_config' "$generated" \
    "generated Django callback must stage protected runtime configuration"
require_text 'service_environment_value "$1" REPO_PATH' "$generated" \
    "repository paths must come from rendered service settings"
require_text 'service_environment_value "$1" INSTALL_PATH' "$generated" \
    "installation paths must come from rendered service settings"
require_text '--build-arg APP_PORT="$(service_environment_value' "$generated" \
    "Django builds must receive the settings-owned application port"
require_text '--build-arg APP_REPO_PATH="$(service_repo_path' "$generated" \
    "Django builds must receive the settings-owned repository path"
require_text 'load_compose_environment_file "$compose_env_file"' "$generated" \
    "installer must load the generated values before host preparation and direct builds"
require_text 'vite_api_url="$(service_environment_value "$service_name" VITE_API_BASE_URL)"' "$generated" \
    "React builds must consume the value rendered into the shared environment"
require_text 'apache_running_mount_permission_spec=()' "$generated" \
    "Apache must declare an explicit running-mount spec"
require_text 'keycloak_running_mount_permission_spec=(' "$generated" \
    "Keycloak must declare a separate running-mount spec"
require_text 'keycloak_db_running_mount_permission_spec=(' "$generated" \
    "Keycloak database must declare its own volume permission spec"
require_text 'keycloak_db' \
    "$repo_root/scaffold/templates/addons/keycloak/container_install/permission-services.txt.tmpl" \
    "Keycloak must own its permission-service declaration"
require_text 'apache' \
    "$repo_root/scaffold/templates/addons/apache/container_install/permission-services.txt.tmpl" \
    "Apache must own its permission-service declaration"

installer_compiler_source="$(sed -n \
    '/^def service_container_installer_compilation(/,/^def deployment_shape(/p' \
    "$repo_root/scripts/scaffold.py")"
if grep -Fq 'DJANGO_TEMPLATE_PATH_SHELL' <<<"$installer_compiler_source"; then
    fail "generic installer compilation must not calculate Django-only paths"
fi
if grep -Fq 'if service["PROFILE"] ==' <<<"$installer_compiler_source"; then
    fail "generic installer compilation must discover profile callbacks"
fi
if grep -Fq 'if addon ==' <<<"$installer_compiler_source"; then
    fail "generic installer compilation must discover add-on callbacks"
fi

previous=0
for section in {1..11}; do
    line="$(grep -n "# $section\." "$generated" | head -n 1 | cut -d: -f1)"
    [ -n "$line" ] && ((line > previous)) || fail "lifecycle section $section is missing or out of order"
    previous="$line"
done

echo "Common container installer template tests passed."
