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
require_text 'write_compose_environment_file' "$template" \
    "common installer must generate the prefixed Compose environment"
require_text 'prepare_host_bind_source_permissions()' "$template" \
    "common installer must expose host permission policy"
require_text 'prepare_running_container_mount_permissions()' "$template" \
    "common installer must expose running-mount permission policy"
require_text '--secret "id=install_conf,src=' "$template" \
    "common installer must build Django with an ephemeral secret"
require_text 'VITE_API_BASE_URL="$vite_api_url"' "$template" \
    "common installer must build React with public Vite configuration"

python3 "$repo_root/scripts/scaffold.py" init "$target" \
    --config "$repo_root/tests/fixtures/mixed_project.json" >/dev/null
generated="$target/container_install.sh"
bash -n "$generated"
require_text 'install_services=(api web)' "$generated" \
    "mixed installer must preserve application order"
require_text 'permission_services=(api web apache keycloak_db keycloak)' "$generated" \
    "mixed installer must include add-ons in permission repair"
require_text 'api) echo django' "$generated" \
    "mixed installer must dispatch the Django profile"
require_text 'web) echo react-vite' "$generated" \
    "mixed installer must dispatch the React profile"
require_text 'stage_container_runtime_config' "$generated" \
    "generated Django callback must stage protected runtime configuration"
require_text 'apache_running_mount_permission_spec=()' "$generated" \
    "Apache must declare an explicit running-mount spec"
require_text 'keycloak_running_mount_permission_spec=(' "$generated" \
    "Keycloak must declare a separate running-mount spec"
require_text 'keycloak_db_running_mount_permission_spec=(' "$generated" \
    "Keycloak database must declare its own volume permission spec"

previous=0
for section in {1..11}; do
    line="$(grep -n "# $section\." "$generated" | head -n 1 | cut -d: -f1)"
    [ -n "$line" ] && ((line > previous)) || fail "lifecycle section $section is missing or out of order"
    previous="$line"
done

echo "Common container installer template tests passed."
