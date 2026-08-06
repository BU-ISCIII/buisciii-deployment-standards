#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

django_target="$work_dir/django-app"
react_target="$work_dir/react-app"
django_config="$work_dir/django.json"
react_config="$work_dir/react.json"
legacy_config="$work_dir/legacy.json"
cp "$repo_root/scaffold/project.json.example" "$django_config"
sed 's/"PROFILE": "django"/"PROFILE": "react-vite"/' \
    "$django_config" > "$react_config"
printf '%s\n' '{"PROFILE":"django"}' > "$legacy_config"

if python3 "$repo_root/scripts/scaffold.py" init "$work_dir/legacy-app" \
    --config "$legacy_config" >/dev/null 2>&1; then
    echo "FAIL: new initialization must require the canonical SERVICES schema" >&2
    exit 1
fi

python3 "$repo_root/scripts/scaffold.py" init "$django_target" \
    --config "$django_config" >/dev/null
test -f "$django_target/install.sh"
test -f "$django_target/conf/template_settings.py"
grep -Fq 'RUN --mount=type=secret,id=install_conf' "$django_target/Dockerfile"
bash -n "$django_target/container_install.sh"
bash -n "$django_target/install.sh"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose -f "$django_target/docker-compose.test.yml" config --quiet
fi

python3 "$repo_root/scripts/scaffold.py" init "$react_target" \
    --config "$react_config" >/dev/null
test ! -e "$react_target/install.sh"
test ! -e "$react_target/conf/template_settings.py"
test -f "$react_target/nginx.conf"
grep -Fq 'FROM docker.io/library/node:22-alpine AS build' "$react_target/Dockerfile"
grep -Fq 'FROM docker.io/nginxinc/nginx-unprivileged:1.27-alpine' \
    "$react_target/Dockerfile"
bash -n "$react_target/container_install.sh"
sh -n "$react_target/scripts/container_start.sh"
bash -n "$react_target/scripts/smoke_test.sh"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose -f "$react_target/docker-compose.test.yml" config --quiet
fi

# Outer deployment structure is common regardless of the selected framework.
diff <(grep '^## ' "$django_target/README.md") \
    <(grep '^## ' "$react_target/README.md") >/dev/null
diff <(grep '^## ' "$django_target/LEAME.md") \
    <(grep '^## ' "$react_target/LEAME.md") >/dev/null
diff <(grep '^# [0-9][0-9]*\.' "$django_target/container_install.sh") \
    <(grep '^# [0-9][0-9]*\.' "$react_target/container_install.sh") >/dev/null
cmp "$django_target/.dockerignore" "$react_target/.dockerignore" >/dev/null

test ! -e "$repo_root/scaffold/templates/profiles/django/container_install.sh.tmpl"
test ! -e "$repo_root/scaffold/templates/profiles/react-vite/container_install.sh.tmpl"
test ! -e "$repo_root/scaffold/templates/profiles/django/README.md.tmpl"
test ! -e "$repo_root/scaffold/templates/profiles/react-vite/README.md.tmpl"

if python3 "$repo_root/scripts/scaffold.py" sync "$django_target" \
    --config "$react_config" >/dev/null 2>&1; then
    echo "FAIL: sync must reject changing an initialized framework profile" >&2
    exit 1
fi

echo "Scaffold profile generation tests passed."
