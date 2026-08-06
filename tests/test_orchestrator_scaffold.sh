#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="$(mktemp -d)"
trap 'rm -rf "$target"' EXIT

python3 "$repo_root/scripts/scaffold.py" init "$target" \
    --config "$repo_root/tests/fixtures/mixed_project.json" >/dev/null

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
grep -Fq 'api_static:' "$prod"
grep -Fq 'api_test_db:' "$test_compose"
grep -Fq 'api_static:/var/www/api/static:ro,z' "$prod"
grep -Fq '${API_HOST_DATA_PATH:?API_HOST_DATA_PATH is required}/documents:/var/www/api/documents:ro,Z' "$prod"
grep -Fq 'REQUIRED generated read-only configuration bind sources' "$prod"
grep -Fq 'OPTIONAL APP MOUNTS belong in ADDONS.apache.MOUNTS' "$prod"
grep -Fq 'APACHE_FORWARDED_PROTO: ${APACHE_FORWARDED_PROTO:-https}' "$prod"

test -f "$target/deployment/apache/00-logs.conf"
test -f "$target/deployment/apache/01-reverse-proxy.conf"
test -f "$target/deployment/apache/02-server-status.conf"
test -f "$target/Dockerfile"
grep -Fq 'FROM docker.io/library/node:22-alpine AS build' "$target/Dockerfile"
grep -Fq 'ServerName api.example.test' \
    "$target/deployment/apache/01-reverse-proxy.conf"
grep -Fq 'ServerName web.example.test' \
    "$target/deployment/apache/01-reverse-proxy.conf"
grep -Fq 'ServerName id.example.test' \
    "$target/deployment/apache/01-reverse-proxy.conf"
grep -Fq 'ProxyPass / http://api:8000/' "$target/deployment/apache/01-reverse-proxy.conf"
grep -Fq 'ProxyPass / http://web:8080/' "$target/deployment/apache/01-reverse-proxy.conf"
grep -Fq 'ProxyPass / http://keycloak:8080/' "$target/deployment/apache/01-reverse-proxy.conf"
grep -Fq 'AllowEncodedSlashes NoDecode' "$target/deployment/apache/01-reverse-proxy.conf"
grep -Fq 'LimitRequestBody ${APACHE_LIMIT_REQUEST_BODY}' "$target/deployment/apache/01-reverse-proxy.conf"
test -f "$target/conf/apache_production_settings.txt"
test -f "$target/conf/apache_test_settings.txt"
test -f "$target/conf/keycloak_production_settings.txt"
test -f "$target/conf/keycloak_test_settings.txt"

# Add-ons and profile fragments are assembled into the final files; they are
# not emitted as operator-facing Compose overlays.
test "$(find "$target" -name 'docker-compose*.yml' -type f | wc -l)" -eq 2
bash -n "$target/container_install.sh"
bash -n "$target/scripts/smoke_test.sh"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose -f "$test_compose" config --quiet
fi

python3 "$repo_root/scripts/scaffold.py" sync "$target" >/dev/null
test ! -e "$prod.bu-isciii-update"

echo "Mixed-profile orchestrator scaffold tests passed."
