#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

sed 's/"ADDONS": {}/"ADDONS": {"mailpit": {"CONFIG_SERVICE": "example-app", "MODES": ["test"]}}/' \
    "$repo_root/scaffold/project.json.example" > "$work_dir/mailpit.json"
python3 "$repo_root/scripts/scaffold.py" init "$work_dir/app" \
    --config "$work_dir/mailpit.json" >/dev/null

test -f "$work_dir/app/conf/mailpit/mailpit_test_settings.txt"
test -f "$work_dir/app/conf/mailpit/mailpit_production_settings.txt"
grep -Fq 'MAILPIT_SMTP_PORT' "$work_dir/app/conf/mailpit/mailpit_test_settings.txt"
grep -Fq 'axllent/mailpit:v1.27' "$work_dir/app/docker-compose.test.yml"
grep -Fq '      - mailpit' "$work_dir/app/docker-compose.test.yml"
if grep -Fq 'axllent/mailpit:v1.27' "$work_dir/app/docker-compose.prod.yml"; then
    fail "Mailpit must not be included in the production Compose topology"
fi

echo "Mailpit add-on scaffold tests passed."
