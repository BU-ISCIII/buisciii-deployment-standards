#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="$(mktemp -d)"
addons_target="$(mktemp -d)"
oidc_only_target="$(mktemp -d)"
oidc_only_config="$(mktemp)"
trap 'rm -rf "$target" "$addons_target" "$oidc_only_target"; rm -f "$oidc_only_config"' EXIT

python3 "$repo_root/scripts/scaffold.py" init "$target" \
    --config "$repo_root/scaffold/project.json.example" >/dev/null

grep -Fq 'RUN --mount=type=secret,id=install_conf' "$target/Dockerfile"
grep -Fq 'USE_INSTALL_CONF_SECRET=false' "$target/Dockerfile"
grep -Fq 'RENDER_DJANGO_SETTINGS: "false"' "$target/docker-compose.prod.yml"
grep -Fq 'RENDER_DJANGO_SETTINGS: "true"' "$target/docker-compose.test.yml"
grep -Fq 'conf/*settings*.txt' "$target/.dockerignore"
grep -Fq '!conf/docker_test_settings.txt' "$target/.dockerignore"
grep -Fq 'node_modules/' "$target/.dockerignore"
grep -Fq 'node_modules/' "$target/.gitignore"
grep -Fq '.next/' "$target/.gitignore"

python3 "$repo_root/scripts/scaffold.py" init "$addons_target" \
    --config "$repo_root/scaffold/project.addons.json.example" >/dev/null

grep -Fq "API_CORS_ALLOWED_ORIGINS='https://CHANGE_ME'" \
    "$addons_target/conf/docker_production_settings.txt"
grep -Fq "OIDC_ISSUER='https://CHANGE_ME/realms/CHANGE_ME'" \
    "$addons_target/conf/docker_production_settings.txt"
grep -Fq 'API_CORS_ALLOWED_ORIGINS:' "$addons_target/docker-compose.prod.yml"
grep -Fq 'OIDC_ISSUER:' "$addons_target/docker-compose.prod.yml"
grep -Fq "KEYCLOAK_ADMIN_API_BASE_URL='https://CHANGE_ME'" \
    "$addons_target/conf/docker_production_settings.txt"
grep -Fq 'KEYCLOAK_ADMIN_API_BASE_URL:' "$addons_target/docker-compose.prod.yml"
grep -Fq '# BEGIN BU-ISCIII ADDON: apache' \
    "$addons_target/docker-compose.prod.yml"
grep -Fq '# BEGIN BU-ISCIII ADDON: keycloak' \
    "$addons_target/docker-compose.prod.yml"
test -f "$addons_target/conf/apache/01-reverse-proxy.conf"
grep -Fq 'apache_config_service=app' "$addons_target/container_install.sh"

sed 's/"ADMIN_ACCESS": true/"ADMIN_ACCESS": false/' \
    "$repo_root/scaffold/project.addons.json.example" > "$oidc_only_config"
python3 "$repo_root/scripts/scaffold.py" init "$oidc_only_target" \
    --config "$oidc_only_config" >/dev/null
grep -Fq 'OIDC_ISSUER=' "$oidc_only_target/conf/docker_production_settings.txt"
if rg -q 'KEYCLOAK_ADMIN_API_' "$oidc_only_target/conf/docker_production_settings.txt" \
    "$oidc_only_target/conf/template_settings.py" \
    "$oidc_only_target/docker-compose.prod.yml"; then
    echo "FAIL: Keycloak Admin API settings leaked into an OIDC-only project" >&2
    exit 1
fi

echo "Build secret and common Docker ignore contract tests passed."
