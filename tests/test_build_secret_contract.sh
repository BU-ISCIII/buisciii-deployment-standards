#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="$(mktemp -d)"
addons_target="$(mktemp -d)"
trap 'rm -rf "$target" "$addons_target"' EXIT

python3 "$repo_root/scripts/scaffold.py" init "$target" \
    --config "$repo_root/scaffold/project.json.example" >/dev/null

grep -Fq 'RUN --mount=type=secret,id=install_conf' "$target/Dockerfile"
grep -Fq 'USE_INSTALL_CONF_SECRET=false' "$target/Dockerfile"
grep -Fq 'RENDER_DJANGO_SETTINGS: "false"' "$target/docker-compose.prod.yml"
grep -Fq 'RENDER_DJANGO_SETTINGS: "true"' "$target/docker-compose.test.yml"
grep -Fq 'conf/*settings*.txt' "$target/.dockerignore"
grep -Fq '!conf/docker_test_settings.txt' "$target/.dockerignore"
grep -Fq 'node_modules/' "$target/.dockerignore"

python3 "$repo_root/scripts/scaffold.py" init "$addons_target" \
    --config "$repo_root/scaffold/project.addons.json.example" >/dev/null

grep -Fq "API_CORS_ALLOWED_ORIGINS='https://CHANGE_ME'" \
    "$addons_target/conf/docker_production_settings.txt"
grep -Fq "OIDC_ISSUER='https://CHANGE_ME/realms/CHANGE_ME'" \
    "$addons_target/conf/docker_production_settings.txt"
grep -Fq 'API_CORS_ALLOWED_ORIGINS:' "$addons_target/docker-compose.prod.yml"
grep -Fq 'OIDC_ISSUER:' "$addons_target/docker-compose.prod.yml"
grep -Fq '# BEGIN BU-ISCIII ADDON: apache' \
    "$addons_target/docker-compose.prod.yml"
grep -Fq '# BEGIN BU-ISCIII ADDON: keycloak' \
    "$addons_target/docker-compose.prod.yml"
test -f "$addons_target/conf/apache/01-reverse-proxy.conf"
grep -Fq 'apache_config_service=app' "$addons_target/container_install.sh"

echo "Build secret and common Docker ignore contract tests passed."
