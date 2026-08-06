#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="$(mktemp -d)"
trap 'rm -rf "$target"' EXIT

python3 "$repo_root/scripts/scaffold.py" init "$target" \
    --config "$repo_root/scaffold/project.json.example" >/dev/null

grep -Fq 'RUN --mount=type=secret,id=install_conf' "$target/Dockerfile"
grep -Fq 'USE_INSTALL_CONF_SECRET=false' "$target/Dockerfile"
grep -Fq 'RENDER_DJANGO_SETTINGS: "false"' "$target/docker-compose.prod.yml"
grep -Fq 'RENDER_DJANGO_SETTINGS: "true"' "$target/docker-compose.test.yml"
grep -Fq 'conf/*settings*.txt' "$target/.dockerignore"
grep -Fq '!conf/docker_test_settings.txt' "$target/.dockerignore"
grep -Fq 'node_modules/' "$target/.dockerignore"

echo "Build secret and common Docker ignore contract tests passed."
