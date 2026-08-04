#!/usr/bin/env python3
"""Create or safely synchronize a BU-ISCIII deployment baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "scaffold" / "templates"
STATE_DIR = ".bu-isciii-deployment"
STATE_FILE = "state.json"
TOKEN = re.compile(r"{{([A-Z0-9_]+)}}")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as handle:
        values = json.load(handle)
    if not isinstance(values, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return {str(key): str(value) for key, value in values.items()}


def render(template: Path, values: dict[str, str]) -> bytes:
    text = template.read_text(encoding="utf-8")
    missing = sorted(set(TOKEN.findall(text)) - values.keys())
    if missing:
        raise ValueError(f"{template}: missing values: {', '.join(missing)}")
    return TOKEN.sub(lambda match: values[match.group(1)], text).encode()


def destination_for(template: Path) -> Path:
    relative = template.relative_to(TEMPLATES)
    name = relative.name.removesuffix(".tmpl")
    return relative.with_name(name)


def load_state(target: Path) -> dict:
    state_path = target / STATE_DIR / STATE_FILE
    if not state_path.exists():
        return {"standard_version": None, "files": {}}
    return json.loads(state_path.read_text(encoding="utf-8"))


def write_state(target: Path, config: dict[str, str], files: dict[str, str]) -> None:
    state_dir = target / STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "standard_version": "0.1.0",
        "source": "BU-ISCIII deployment standards",
        "config": config,
        "files": files,
    }
    (state_dir / STATE_FILE).write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def executable(relative: Path) -> bool:
    return relative.as_posix() in {
        "install.sh",
        "container_install.sh",
        "scripts/container_start.sh",
        "scripts/smoke_test.sh",
    }


def synchronize(target: Path, config: dict[str, str], initial: bool) -> int:
    state = load_state(target)
    old_hashes = state.get("files", {})
    new_hashes: dict[str, str] = {}
    conflicts = 0

    for template in sorted(TEMPLATES.rglob("*.tmpl")):
        relative = destination_for(template)
        destination = target / relative
        content = render(template, config)
        new_hash = digest(content)
        old_hash = old_hashes.get(relative.as_posix())
        current_hash = digest(destination.read_bytes()) if destination.exists() else None

        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or current_hash == old_hash:
            destination.write_bytes(content)
            if executable(relative):
                destination.chmod(destination.stat().st_mode | 0o111)
            print(f"updated  {relative}")
        elif current_hash == new_hash:
            print(f"current  {relative}")
        else:
            candidate = destination.with_name(destination.name + ".bu-isciii-update")
            candidate.write_bytes(content)
            print(f"conflict {relative} -> {candidate.name}")
            conflicts += 1

        new_hashes[relative.as_posix()] = new_hash

    # The recorded hash is the latest central baseline, not a conflicting local file.
    write_state(target, config, new_hashes)
    verb = "Initialized" if initial else "Synchronized"
    print(f"{verb} {target} with {conflicts} conflict(s).")
    return 2 if conflicts else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "sync"):
        sub = subparsers.add_parser(command)
        sub.add_argument("target", type=Path)
        sub.add_argument("--config", type=Path)
    args = parser.parse_args()

    target = args.target.resolve()
    state = load_state(target)
    if args.config:
        config = load_json(args.config.resolve())
    elif args.command == "sync" and state.get("config"):
        config = state["config"]
    else:
        parser.error("--config is required for init and for sync without saved state")

    if args.command == "init" and (target / STATE_DIR / STATE_FILE).exists():
        parser.error(f"{target} is already initialized; use sync")
    target.mkdir(parents=True, exist_ok=True)
    return synchronize(target, config, args.command == "init")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
