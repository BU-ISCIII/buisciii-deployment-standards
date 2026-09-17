#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixtures="$repo_root/tests/fixtures/check_config"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
# shellcheck disable=SC1091
source "$repo_root/lib/container/common.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }

services=(pathocore-web=nextjs pathocore-api=django mepram-omop-api=django)
check_output=""
check_status=0

# Run the checker through the shared library function exactly as the installer
# does. Arguments: mode, environment file, optional Apache directory override.
run_check() {
    local mode="$1" env_file="$2" apache_dir="${3:-$fixtures/apache}"
    check_status=0
    check_output="$(check_deployment_configuration "$mode" "$env_file" \
        "$fixtures/compose.prod.yml" "$apache_dir" "${services[@]}" 2>&1)" \
        || check_status=$?
}

# Replace base settings with the KEY='value' lines of one override file.
merge_environment() {
    local override="$1" output="$2" key
    cp "$fixtures/valid.env" "$output"
    while IFS= read -r key; do
        grep -v "^$key=" "$output" > "$output.tmp" || true
        mv "$output.tmp" "$output"
    done < <(sed -nE 's/^([A-Z_][A-Z0-9_]*)=.*/\1/p' "$override")
    grep -E '^[A-Z_][A-Z0-9_]*=' "$override" >> "$output"
}

run_check production "$fixtures/valid.env"
[ "$check_status" -eq 0 ] || fail "valid configuration must pass: $check_output"
grep -Fq '0 error(s), 0 warning(s)' <<<"$check_output" \
    || fail "valid configuration must not warn: $check_output"

case_count=0
for override in "$fixtures"/cases/*.env; do
    rule="$(basename "$override" .env)"
    merge_environment "$override" "$work/$rule.env"
    run_check production "$work/$rule.env"
    [ "$check_status" -eq 1 ] \
        || fail "$rule must fail production (status $check_status): $check_output"
    grep -Fq "ERROR [$rule]" <<<"$check_output" \
        || fail "$rule must be reported: $check_output"
    case_count=$((case_count + 1))
done
documented_rules="$(sed -nE 's/^  ([a-z]+(-[a-z]+)+)  .*/\1/p' \
    "$repo_root/lib/container/check_config.py" | sort)"
fixture_rules="$(for override in "$fixtures"/cases/*.env; do basename "$override" .env; done | sort)"
[ "$documented_rules" = "$fixture_rules" ] \
    || fail "every documented rule needs exactly one failing fixture"

# A misspelled host still has its port checked against the suggested service.
printf "PATHOCORE_WEB_MEPRAM_OMOP_API_PROXY_TARGET='http://mepram_omop_api:8001'\n" \
    > "$work/host-and-port.override"
merge_environment "$work/host-and-port.override" "$work/host-and-port.env"
run_check production "$work/host-and-port.env"
grep -Fq 'ERROR [unknown-host]' <<<"$check_output" \
    && grep -Fq "ERROR [upstream-port] PATHOCORE_WEB_MEPRAM_OMOP_API_PROXY_TARGET='http://mepram_omop_api:8001': mepram-omop-api listens on 8004" <<<"$check_output" \
    || fail "host and port mistakes must be reported together: $check_output"

# Test settings use shortcuts, so the same finding only warns.
run_check test "$work/upstream-port.env"
[ "$check_status" -eq 0 ] || fail "test mode must not fail: $check_output"
grep -Fq 'WARNING [upstream-port]' <<<"$check_output" \
    || fail "test mode must still report findings: $check_output"

# A single-label host without a similar Compose service may be institutional DNS.
printf "MEPRAM_OMOP_API_DB_HOST='dbserver'\n" > "$work/dns.override"
merge_environment "$work/dns.override" "$work/dns.env"
run_check production "$work/dns.env"
[ "$check_status" -eq 0 ] || fail "unconfirmed hosts must only warn: $check_output"
grep -Fq 'WARNING [unknown-host]' <<<"$check_output" \
    || fail "unconfirmed hosts must be reported: $check_output"

# Secrets and URL credentials never reach the installer output.
printf "PATHOCORE_WEB_MEPRAM_OMOP_API_PROXY_TARGET='http://svc-user:url-secret@mepram-omop-api:9000'\nPATHOCORE_API_DB_PASSWORD='CHANGE_ME-db-secret'\n" \
    > "$work/secret.override"
merge_environment "$work/secret.override" "$work/secret.env"
run_check production "$work/secret.env"
grep -Fq 'ERROR [upstream-port]' <<<"$check_output" \
    || fail "credentialed URL must still be checked: $check_output"
grep -Fq 'ERROR [unresolved-placeholder] PATHOCORE_API_DB_PASSWORD' <<<"$check_output" \
    || fail "placeholder must be reported by key: $check_output"
if grep -Eq 'url-secret|svc-user|db-secret' <<<"$check_output"; then
    fail "checker output must not contain secret values: $check_output"
fi

# Server-side Keycloak calls may use internal routes; browser URLs may not.
printf "PATHOCORE_API_KEYCLOAK_ADMIN_API_BASE_URL='http://host.docker.internal:8081'\nMEPRAM_OMOP_API_OIDC_JWKS_URL='http://127.0.0.1:8081/realms/pathocore/protocol/openid-connect/certs'\n" \
    > "$work/internal-keycloak.override"
merge_environment "$work/internal-keycloak.override" "$work/internal-keycloak.env"
run_check production "$work/internal-keycloak.env"
[ "$check_status" -eq 0 ] || fail "internal server-side Keycloak routes must pass: $check_output"
printf "PATHOCORE_WEB_NEXT_PUBLIC_KEYCLOAK_URL='http://pathocore-web-keycloak:8080'\n" \
    > "$work/internal-browser.override"
merge_environment "$work/internal-browser.override" "$work/internal-browser.env"
run_check production "$work/internal-browser.env"
grep -Fq 'ERROR [keycloak-origin]' <<<"$check_output" \
    || fail "browser Keycloak URLs must use the public origin: $check_output"

# Apache routes are optional; without them the ServerName requirement disappears.
merge_environment "$fixtures/cases/allowed-hosts.env" "$work/no-apache.env"
run_check production "$work/no-apache.env" "$work/missing-apache"
[ "$check_status" -eq 0 ] || fail "missing Apache directory must be ignored: $check_output"

# Apache ProxyPass targets are validated like environment URLs.
mkdir -p "$work/apache"
sed 's#http://pathocore-web:3000/#http://pathocore-web:8080/#' \
    "$fixtures/apache/01-reverse-proxy.conf" > "$work/apache/01-reverse-proxy.conf"
run_check production "$fixtures/valid.env" "$work/apache"
grep -Fq 'ERROR [upstream-port] Apache ProxyPass 01-reverse-proxy.conf:' <<<"$check_output" \
    || fail "Apache upstream ports must be checked: $check_output"

# The checker must be distributed with the vendored shell libraries.
python3 "$repo_root/scripts/scaffold.py" init "$work/generated" \
    --config "$repo_root/tests/fixtures/mixed_project.json" >/dev/null
[ -f "$work/generated/deployment/lib/container/check_config.py" ] \
    || fail "scaffold must vendor check_config.py"
python3 "$repo_root/scripts/scaffold.py" check-lib "$work/generated" >/dev/null \
    || fail "vendored checker must match the central copy"

echo "Deployment configuration checker tests passed ($case_count rule fixtures)."
