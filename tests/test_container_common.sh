#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$repo_root/lib/container/common.sh"
# shellcheck disable=SC1091
source "$repo_root/lib/container/django.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }
assert_equal() {
    local expected="$1" actual="$2" description="$3"
    [ "$expected" = "$actual" ] \
        || fail "$description: expected '$expected', got '$actual'"
}

assert_equal "example.org" "$(normalize_apache_server_name 'https://example.org:8443/path')" \
    "normalize HTTPS server name"
assert_equal "localhost" "$(normalize_apache_server_name '*')" \
    "normalize wildcard server name"
assert_equal 'a\|b\&c\\d' "$(sed_replacement_escape 'a|b&c\d')" \
    "escape sed replacement"
assert_equal 'a\.b\[c\]' "$(sed_search_escape 'a.b[c]')" \
    "escape sed search"

(
    settings_fixture="$(mktemp)"
    printf "REQUIRED_VALUE='from-file'\n" > "$settings_fixture"
    assert_equal "from-file" "$(config_value REQUIRED_VALUE "$settings_fixture")" \
        "read required configuration value"
    if config_value MISSING_VALUE "$settings_fixture" 2>/dev/null; then
        fail "missing required configuration value must fail"
    fi
    rm -f "$settings_fixture"
)

array_contains app db app worker || fail "find array member"
if array_contains missing db app worker; then fail "reject missing array member"; fi
array_contains 'service with spaces' app 'service with spaces' \
    || fail "find array member containing spaces"
if array_contains app; then fail "empty candidate array must not match"; fi

(
    compose_fixture="$(mktemp)"
    compose_validation_call=""
    compose_with_env_exec() { compose_validation_call="$*"; }
    require_compose_file "$compose_fixture"
    validate_compose_configuration "$compose_fixture"
    assert_equal "-f $compose_fixture config --quiet" "$compose_validation_call" \
        "Compose configuration validation arguments"
    if require_compose_file "$compose_fixture.missing" 2>/dev/null; then
        fail "missing Compose file must fail validation"
    fi
    rm -f "$compose_fixture"
)

(
    runtime_conf="$(mktemp)"
    runtime_calls=()
    engine_exec() { runtime_calls+=("$*"); }
    stage_container_runtime_config \
        app-container "$runtime_conf" /srv/app/runtime-settings.txt 1212 3434
    assert_equal "cp $runtime_conf app-container:/srv/app/runtime-settings.txt" \
        "${runtime_calls[0]}" "runtime configuration copy"
    assert_equal "exec --user 0 app-container chown 1212:3434 /srv/app/runtime-settings.txt" \
        "${runtime_calls[1]}" "runtime configuration ownership"
    assert_equal "exec --user 0 app-container chmod 0600 /srv/app/runtime-settings.txt" \
        "${runtime_calls[2]}" "runtime configuration restrictive mode"
    remove_container_runtime_config app-container /srv/app/runtime-settings.txt
    assert_equal "exec --user 0 app-container rm -f -- /srv/app/runtime-settings.txt" \
        "${runtime_calls[3]}" "runtime configuration removal"
    if remove_container_runtime_config app-container / 2>/dev/null; then
        fail "runtime configuration removal must reject root path"
    fi
    rm -f "$runtime_conf"
)

(
    smoke_fixture="$(mktemp)"
    smoke_call=""
    bash() { smoke_call="$*"; }
    run_standard_smoke_test \
        "$smoke_fixture" test podman compose.test.yml ""
    assert_equal "$smoke_fixture --engine podman --compose_file compose.test.yml --test" \
        "$smoke_call" "test smoke invocation"
    run_standard_smoke_test \
        "$smoke_fixture" production docker compose.prod.yml .env.prod.file --skip_http
    assert_equal "$smoke_fixture --engine docker --compose_file compose.prod.yml --env_file .env.prod.file --skip_http" \
        "$smoke_call" "production smoke invocation"
    rm -f "$smoke_fixture"
)

(
    permission_root="$(mktemp -d)"
    permission_file="$permission_root/file with spaces"
    permission_missing="$permission_root/not-created"
    printf 'test\n' > "$permission_file"
    permission_calls=()
    chown_with_podman_fallback() { permission_calls+=("chown|$1|$2"); }
    chmod_with_podman_fallback() { permission_calls+=("chmod|$1|$2"); }
    host_permission_spec=(
        "$permission_file|1212:3434|0664"
        "$permission_root|-|0755"
        "$permission_missing|1001:0|0775"
    )
    apply_host_permission_spec "${host_permission_spec[@]}"
    assert_equal "chown|1212:3434|$permission_file" "${permission_calls[0]}" \
        "permission specification ownership"
    assert_equal "chmod|0664|$permission_file" "${permission_calls[1]}" \
        "permission specification file mode"
    assert_equal "chmod|0755|$permission_root" "${permission_calls[2]}" \
        "permission specification owner-preserving mode"
    assert_equal "3" "${#permission_calls[@]}" \
        "missing permission specification paths are skipped"
    if apply_host_permission_spec "$permission_file|1212:3434" 2>/dev/null; then
        fail "malformed permission specification must fail"
    fi
    rm -f "$permission_file"
    rmdir "$permission_root"
)

(
    container_permission_calls=()
    engine_exec() { container_permission_calls+=("$*"); }
    apply_container_directory_permission_spec app-container \
        '/opt/app/logs|1212:3434|u+rwX,g+rwX' \
        '/opt/app/static|1212:3434|u+rwX,g+rwX,o+rX'
    assert_equal "2" "${#container_permission_calls[@]}" \
        "container directory permission entry count"
    case "${container_permission_calls[0]}" in
        *"app-container"*"/opt/app/logs"*"1212:3434"*"u+rwX,g+rwX"*) ;;
        *) fail "container directory permissions must forward path, owner, and mode" ;;
    esac
    if apply_container_directory_permission_spec app-container \
        '/opt/app/logs|1212:3434' 2>/dev/null; then
        fail "malformed container directory permission specification must fail"
    fi
)

staging_context="$(mktemp -d)"
external_settings="$(mktemp --suffix=_settings.txt)"
printf 'INSTALL_PATH=/opt/example\n' > "$external_settings"
prepared_host=""
prepared_relative=""
prepared_temp=""
prepare_install_configuration \
    "$external_settings" "$repo_root" "$staging_context" app production \
    prepared_host prepared_relative prepared_temp
assert_equal "$prepared_temp" "$prepared_host" "staged configuration host path"
assert_equal "$(basename "$prepared_temp")" "$prepared_relative" \
    "staged configuration context-relative path"
[ -f "$prepared_temp" ] || fail "temporary staged configuration must exist"
cleanup_files "$prepared_temp" "$external_settings"

mkdir -p "$staging_context/conf"
internal_settings="$staging_context/conf/docker_test_settings.txt"
printf 'INSTALL_PATH=/opt/example\n' > "$internal_settings"
prepare_install_configuration \
    conf/docker_test_settings.txt "$staging_context" "$staging_context" app test \
    prepared_host prepared_relative prepared_temp
assert_equal "$internal_settings" "$prepared_host" "in-context configuration host path"
assert_equal "conf/docker_test_settings.txt" "$prepared_relative" \
    "in-context configuration relative path"
assert_equal "" "$prepared_temp" "in-context configuration needs no temporary copy"
cleanup_files "$internal_settings"
rmdir "$staging_context/conf" "$staging_context"

invalid_production_conf="$(mktemp --suffix=.txt)"
printf 'INSTALL_PATH=/opt/example\n' > "$invalid_production_conf"
invalid_context="$(mktemp -d)"
if prepare_install_configuration \
    "$invalid_production_conf" "$repo_root" "$invalid_context" app production \
    prepared_host prepared_relative prepared_temp 2>/dev/null; then
    fail "production configuration without settings in its name must fail"
fi
cleanup_files "$invalid_production_conf"
rmdir "$invalid_context"

test_conf="$(mktemp)"
trap 'rm -f "$test_conf"' EXIT
printf '%s\n' \
    "FOO='first'" \
    'IGNORED=value' \
    'FOO="last" # comment' > "$test_conf"
assert_equal "last" "$(read_install_conf_value FOO "$test_conf")" \
    "read last configuration value"
assert_equal "" "$(read_install_conf_value MISSING "$test_conf")" \
    "missing configuration value"

compose_env_test_dir="$(mktemp -d)"
platform_settings="$compose_env_test_dir/platform_settings.txt"
iskylims_settings="$compose_env_test_dir/iskylims_settings.txt"
compose_env_output="$compose_env_test_dir/.env.production.file"
printf '%s\n' "APP_UID='1212'" "APP_PORT='8000'" > "$platform_settings"
printf '%s\n' "APP_UID='1213'" "APP_PORT='8001'" > "$iskylims_settings"
compose_settings_sources=(
    "PLATFORM|$platform_settings"
    "ISKYLIMS|$iskylims_settings"
)
compose_explicit_values=(
    "GIT_REVISION|current"
    "DISPLAY_NAME|two services"
)
write_compose_environment_file \
    "$compose_env_output" compose_settings_sources compose_explicit_values
grep -Fq "PLATFORM_APP_UID='1212'" "$compose_env_output" \
    || fail "prefix Platform settings in Compose environment"
grep -Fq "ISKYLIMS_APP_PORT='8001'" "$compose_env_output" \
    || fail "prefix iSkyLIMS settings in Compose environment"
unset PLATFORM_APP_UID ISKYLIMS_APP_PORT
load_compose_environment_file "$compose_env_output"
assert_equal "1212" "$PLATFORM_APP_UID" \
    "load first service value from generated Compose environment"
assert_equal "8001" "$ISKYLIMS_APP_PORT" \
    "load second service value from generated Compose environment"
grep -Fq "DISPLAY_NAME='two services'" "$compose_env_output" \
    || fail "quote explicit Compose environment values"
assert_equal "600" "$(stat -c %a "$compose_env_output")" \
    "protect generated Compose environment file"
duplicate_compose_values=("PLATFORM_APP_UID|9999")
if write_compose_environment_file \
    "$compose_env_test_dir/duplicate.env" compose_settings_sources \
    duplicate_compose_values 2>/dev/null; then
    fail "duplicate Compose environment variables must fail"
fi
cleanup_files \
    "$platform_settings" "$iskylims_settings" "$compose_env_output" \
    "$compose_env_test_dir/duplicate.env"
rmdir "$compose_env_test_dir"

compose_with_env_exec() {
    assert_equal "-f" "$1" "Compose image lookup file flag"
    assert_equal "compose.example.yml" "$2" "Compose image lookup file"
    assert_equal "images" "$3" "Compose image lookup operation"
    assert_equal "-q" "$4" "Compose image lookup quiet flag"
    assert_equal "app" "$5" "Compose image lookup service"
    printf '%s\n' old-image-id selected-image-id
}
assert_equal "selected-image-id" "$(compose_service_image_id compose.example.yml app)" \
    "resolve Compose service image ID"
prebuild_output="$(print_prebuild_diagnostics \
    'Pre-build diagnostics' "$repo_root" current abc123)"
grep -Fq 'requested revision: current' <<<"$prebuild_output" \
    || fail "combined diagnostics requested revision"
grep -Fq 'image before build: abc123' <<<"$prebuild_output" \
    || fail "combined diagnostics existing image"
image_output="$(print_image_before_diagnostics 'Before:' abc123)"
grep -Fq 'image before build: abc123' <<<"$image_output" \
    || fail "print existing image diagnostics"
image_output="$(print_image_after_diagnostics 'After:' abc123 def456)"
grep -Fq 'image id check: changed' <<<"$image_output" \
    || fail "compare changed image diagnostics"

template_file="$(mktemp)"
rendered_file="$(mktemp)"
settings_template="$(mktemp)"
settings_file="$(mktemp)"
trap 'rm -f "$test_conf" "$template_file" "$rendered_file" "$settings_template" "$settings_file"' EXIT
printf 'alpha=TOKEN\n' > "$template_file"
render_config_template "$template_file" "$rendered_file" 0600 TOKEN 'a&b'
assert_equal 'alpha=a&b' "$(cat "$rendered_file")" "render token template"

printf 'host=${APACHE_SERVER_NAME}\nport=${APP_APP_PORT}\n' > "$template_file"
export APACHE_SERVER_NAME='app.example.test' APP_APP_PORT='8001'
render_environment_config_template "$template_file" "$rendered_file" 0644
assert_equal $'host=app.example.test\nport=8001' "$(cat "$rendered_file")" \
    "render deployment environment template"
unset APACHE_SERVER_NAME APP_APP_PORT
printf 'missing=${NOT_DEFINED_FOR_RENDER_TEST}\n' > "$template_file"
if render_environment_config_template \
    "$template_file" "$rendered_file" 0644 2>/dev/null; then
    fail "environment renderer must reject unresolved variables"
fi

printf '%s\n' \
    'SECRET_KEY = "PLACEHOLDER"' \
    'DB_USER = "djangouser"' \
    'DB_HOST = "djangohost"' > "$settings_template"
printf '%s\n' 'DB_USER=test_user' 'DB_SERVER_IP=db.internal' > "$test_conf"
engine=docker
render_django_settings_file "$settings_template" "$settings_file" "$test_conf"
grep -Fq 'DB_USER = "test_user"' "$settings_file" || fail "Django DB user rendering"
grep -Fq 'DB_HOST = "db.internal"' "$settings_file" || fail "Django DB host rendering"
grep -Eq "^SECRET_KEY = '[^']+'$" "$settings_file" || fail "Django secret rendering"
first_secret="$(grep -E '^SECRET_KEY[[:space:]]*=' "$settings_file")"
printf '%s\n' 'DB_USER=updated_user' 'DB_SERVER_IP=db.internal' > "$test_conf"
render_django_settings_file "$settings_template" "$settings_file" "$test_conf"
assert_equal "$first_secret" "$(grep -E '^SECRET_KEY[[:space:]]*=' "$settings_file")" \
    "preserve Django secret during rerender"
grep -Fq 'DB_USER = "updated_user"' "$settings_file" || fail "Django settings rerender"

service_container_name() { [ "$1" = "app" ] && echo "known_app"; }
django_permission_call=""
engine_exec() {
    if [ "$1" = "inspect" ] && [ "${4:-}" = "known_app" ]; then
        if [ "$3" = '{{.Id}}' ]; then echo abc123; else echo true; fi
        return 0
    fi
    if [ "$1" = "exec" ] && [ "$2" = "--user" ] && [ "$3" = "0" ]; then
        django_permission_call="$*"
        return 0
    fi
    if [ "$1" = "exec" ] && [ "$2" = "known_app" ]; then
        case "${5:-}" in
            *"rev-parse --short HEAD"*) echo abc1234 ;;
            *"rev-parse HEAD"*) echo abc123456789 ;;
            *"git log -1 --oneline"*) echo 'abc1234 test commit' ;;
        esac
        return 0
    fi
    return 1
}
assert_equal "known_app" "$(resolve_service_container app)" \
    "resolve explicit container name"
assert_equal "known_app" "$(ensure_service_running app known_app)" \
    "ensure running container"
prepare_django_container_settings_permissions \
    known_app /opt/app/project/settings.py 1212 3434
case "$django_permission_call" in
    *"known_app"*"/opt/app/project/settings.py"*"1212:3434"*) ;;
    *) fail "Django settings permissions must forward container, path, UID, and GID" ;;
esac
django_permission_call=""
prepare_django_container_settings_permissions known_app "" 1212 3434
assert_equal "" "$django_permission_call" \
    "empty Django settings path skips the container operation"
container_output="$(print_container_repository_diagnostics \
    'Container:' known_app /srv/app abc123456789 abc1234)"
grep -Fq 'HEAD check: OK local=abc1234 container=abc1234' <<<"$container_output" \
    || fail "compare container repository diagnostics"

echo "Shared container library tests passed."
