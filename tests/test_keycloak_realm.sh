#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

sed 's|"ADDONS": {}|"ADDONS": {"keycloak": {"CONFIG_SERVICE": "example-app", "MOUNTS": ["./theme:/opt/keycloak/themes/example:ro,z"]}}|' \
    "$repo_root/scaffold/project.json.example" > "$work_dir/keycloak.json"
python3 "$repo_root/scripts/scaffold.py" init "$work_dir/app" \
    --config "$work_dir/keycloak.json" >/dev/null

realm_config="$work_dir/app/conf/keycloak/realm-test.json"
test -f "$work_dir/app/conf/keycloak/realm-production.json"
test -f "$realm_config"
grep -Fq "KEYCLOAK_REALM_TEMPLATE_PATH='./conf/keycloak/realm-test.json'" \
    "$work_dir/app/conf/keycloak/keycloak_test_settings.txt"
grep -Fq 'render_json_environment_template' "$work_dir/app/container_install.sh"
grep -Fq './theme:/opt/keycloak/themes/example:ro,z' \
    "$work_dir/app/docker-compose.test.yml"
grep -Fq './theme:/opt/keycloak/themes/example:ro,z' \
    "$work_dir/app/docker-compose.prod.yml"
bash -n "$work_dir/app/container_install.sh"

# Local values and arrays belong to the application. Removing a standard key
# must be repairable without replacing either kind of local customization.
python3 - "$realm_config" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    realm = json.load(handle)
realm["registrationAllowed"] = True
realm.pop("resetPasswordAllowed")
realm["clients"] = [{"clientId": "application-web", "enabled": True}]
with open(path, "w", encoding="utf-8") as handle:
    json.dump(realm, handle, indent=2)
    handle.write("\n")
PY

if python3 "$repo_root/scripts/scaffold.py" check "$work_dir/app" \
    > "$work_dir/check.out"; then
    fail "a missing standard realm property must fail check"
fi
grep -Eq '^update-available +conf/keycloak/realm-test.json$' \
    "$work_dir/check.out"
grep -Fq 'missing properties: resetPasswordAllowed' "$work_dir/check.out"

python3 "$repo_root/scripts/scaffold.py" sync "$work_dir/app" \
    > "$work_dir/sync.out"
python3 - "$realm_config" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    realm = json.load(handle)
assert realm["registrationAllowed"] is True
assert realm["resetPasswordAllowed"] is True
assert realm["clients"] == [{"clientId": "application-web", "enabled": True}]
PY
python3 "$repo_root/scripts/scaffold.py" check "$work_dir/app" >/dev/null

echo "Keycloak realm scaffold tests passed."
