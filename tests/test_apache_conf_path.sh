#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
source "$repo_root/lib/container/common.sh"
script_dir="$work/repository"
mkdir -p "$script_dir/conf/apache"
for name in 00-logs.conf 01-reverse-proxy.conf 02-server-status.conf; do
    printf 'ServerName ${APACHE_SERVER_NAME}\n' > "$script_dir/conf/apache/$name"
done
service_environment_value() { printf '8000\n'; }
service_install_path() { printf '/opt/example\n'; }
normalize_apache_server_name() { printf 'example\n'; }
apply_host_permission_spec() { printf '%s\n' "$@" > "$work/permissions"; }
eval "prepare_apache() { $(sed 's/{{CONFIG_SERVICE_SHELL}}/app/g' "$repo_root/scaffold/templates/addons/apache/container_install/create-host-bind-sources.sh.tmpl")
}"
eval "permissions_apache() { $(cat "$repo_root/scaffold/templates/addons/apache/container_install/set-host-bind-permissions.sh.tmpl")
}"
mode=test
APACHE_SERVER_NAME=example.org
APACHE_LOG_PATH="$work/logs"
for APACHE_CONF_PATH in '' "$work/custom apache"; do
    output_dir="${APACHE_CONF_PATH:-$script_dir/deployment/apache}"
    prepare_apache
    permissions_apache
    for name in 00-logs.conf 01-reverse-proxy.conf 02-server-status.conf; do
        grep -Fxq 'ServerName example.org' "$output_dir/$name"
        grep -Fxq "$output_dir/$name|-|0644" "$work/permissions"
    done
    grep -Fxq "$output_dir|-|0755" "$work/permissions"
done
for mode in prod test; do
    for name in 00-logs.conf 01-reverse-proxy.conf 02-server-status.conf; do
        grep -Fq -- "\${APACHE_CONF_PATH:-./deployment/apache}/$name:/etc/httpd/conf.d/$name:ro,z" \
            "$repo_root/scaffold/templates/addons/apache/compose/$mode.service-volumes.yml.tmpl"
    done
done
printf 'Apache configuration path tests passed.\n'
