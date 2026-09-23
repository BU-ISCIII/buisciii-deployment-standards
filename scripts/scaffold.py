#!/usr/bin/env python3
"""Create or safely synchronize a BU-ISCIII deployment baseline.

The core normalizes project topology, renders templates, and merges artifacts.
Framework and infrastructure behavior belongs in profile/add-on templates. When
topology-dependent iteration or validation cannot be expressed by the simple
token renderer, keep that Python in the explicitly marked compiler sections
below and group it by owning profile or add-on.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "scaffold" / "templates"
COMMON_TEMPLATES = TEMPLATES / "common"
COMMON_COMPOSE_TEMPLATE = COMMON_TEMPLATES / "docker-compose.yml.tmpl"
PROFILE_TEMPLATES = TEMPLATES / "profiles"
ADDON_TEMPLATES = TEMPLATES / "addons"
SHARED_LIB = ROOT / "lib"
STATE_DIR = ".bu-isciii-deployment"
STATE_FILE = "state.json"
TOKEN = re.compile(r"{{([A-Z0-9_]+)}}")
APPLICATION_BLOCKS = (
    re.compile(
        rb"(?P<start><!-- BEGIN BU-ISCIII APPLICATION: "
        rb"(?P<name>[a-z0-9-]+) -->\n)"
        rb"(?P<body>.*?)"
        rb"(?P<end><!-- END BU-ISCIII APPLICATION: (?P=name) -->)",
        re.DOTALL,
    ),
    re.compile(
        rb"(?P<start># BEGIN BU-ISCIII APPLICATION: "
        rb"(?P<name>[a-z0-9-]+)\n)"
        rb"(?P<body>.*?)"
        rb"(?P<end># END BU-ISCIII APPLICATION: (?P=name))",
        re.DOTALL,
    ),
)


@dataclass
class ComposeCompilation:
    """Fragments returned by every profile or add-on Compose compiler."""

    service_lines: list[str]
    support_lines: list[str]
    volume_lines: list[str]
    secret_lines: list[str]
    artifacts: list[tuple[Path, bytes]]


@dataclass
class ContainerInstallerCompilation:
    """Topology fragments merged into the common container installer."""

    install_services: list[str] = field(default_factory=list)
    addon_build_services: list[str] = field(default_factory=list)
    permission_services: list[str] = field(default_factory=list)
    configured_services: list[str] = field(default_factory=list)
    default_conf_cases: list[str] = field(default_factory=list)
    build_context_cases: list[str] = field(default_factory=list)
    readiness_cases: list[str] = field(default_factory=list)
    image_cases: list[str] = field(default_factory=list)
    profile_cases: list[str] = field(default_factory=list)
    dockerfile_cases: list[str] = field(default_factory=list)
    container_conf_cases: list[str] = field(default_factory=list)
    settings_sources: list[str] = field(default_factory=list)
    deployment_values: list[str] = field(default_factory=list)
    host_sources: list[str] = field(default_factory=list)
    host_permissions: list[str] = field(default_factory=list)
    running_cases: list[str] = field(default_factory=list)
    bootstrap_cases: list[str] = field(default_factory=list)
    production_build_cases: list[str] = field(default_factory=list)

    def extend(self, other: ContainerInstallerCompilation) -> None:
        """Append another compiler result while preserving declaration order."""
        for field_name in vars(self):
            getattr(self, field_name).extend(getattr(other, field_name))

    def template_values(self) -> dict[str, str]:
        """Convert collected fragments into tokens used by common templates."""
        return {
            "INSTALL_SERVICES_LITERAL": bash_array(self.install_services),
            "ADDON_BUILD_SERVICES_LITERAL": bash_array(self.addon_build_services),
            "PERMISSION_SERVICES_LITERAL": bash_array(self.permission_services),
            "CONFIGURED_SERVICES_LITERAL": bash_array(self.configured_services),
            "DEFAULT_CONF_CASES": "\n".join(self.default_conf_cases),
            "BUILD_CONTEXT_CASES": "\n".join(self.build_context_cases),
            "READINESS_CASES": "\n".join(self.readiness_cases),
            "IMAGE_CASES": "\n".join(self.image_cases),
            "PROFILE_CASES": "\n".join(self.profile_cases),
            "DOCKERFILE_CASES": "\n".join(self.dockerfile_cases),
            "CONTAINER_CONF_CASES": "\n".join(self.container_conf_cases),
            "SETTINGS_SOURCES": "\n".join(self.settings_sources),
            "DEPLOYMENT_VALUES": "\n".join(self.deployment_values),
            "PREPARE_HOST_SOURCES": "\n".join(self.host_sources) or "    return 0",
            "HOST_PERMISSION_SPECS": "\n".join(self.host_permissions) or "    return 0",
            "RUNNING_PERMISSION_CASES": "\n".join(self.running_cases),
            "BOOTSTRAP_CASES": "\n".join(self.bootstrap_cases),
            "PRODUCTION_BUILD_CASES": "\n".join(self.production_build_cases),
        }


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def preserve_application_blocks(expected: bytes, current: bytes | None) -> bytes:
    """Copy explicitly application-owned blocks into a new render."""
    if current is None:
        return expected
    current_blocks: dict[bytes, bytes] = {}
    for pattern in APPLICATION_BLOCKS:
        for match in pattern.finditer(current):
            name = match.group("name")
            if name in current_blocks:
                raise ValueError(f"Duplicate application-owned block: {name.decode()}")
            current_blocks[name] = match.group("body")

    def preserve(match: re.Match[bytes]) -> bytes:
        body = current_blocks.get(match.group("name"), match.group("body"))
        return match.group("start") + body + match.group("end")

    for pattern in APPLICATION_BLOCKS:
        expected = pattern.sub(preserve, expected)
    return expected


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        values = json.load(handle)
    if not isinstance(values, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return {str(key): value for key, value in values.items()}


def scalar_values(config: dict[str, Any]) -> dict[str, str]:
    return {
        str(key): str(value)
        for key, value in config.items()
        if isinstance(value, (str, int, float, bool))
    }


def render(template: Path, values: dict[str, str]) -> bytes:
    text = template.read_text(encoding="utf-8")
    missing = sorted(set(TOKEN.findall(text)) - values.keys())
    if missing:
        raise ValueError(f"{template}: missing values: {', '.join(missing)}")
    return TOKEN.sub(lambda match: values[match.group(1)], text).encode()


def destination_for(template: Path, source_root: Path) -> Path:
    relative = template.relative_to(source_root)
    name = relative.name.removesuffix(".tmpl")
    return relative.with_name(name)


def selected_profile(config: dict[str, Any]) -> str:
    owned = owned_profile_service(config)
    if owned is None:
        raise ValueError(
            "A project profile requires one service with BUILD_CONTEXT '.'"
        )
    profile = str(owned[1].get("PROFILE", "")).strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", profile):
        raise ValueError(f"Invalid PROFILE name: {profile!r}")
    if not (PROFILE_TEMPLATES / profile).is_dir():
        available = ", ".join(
            path.name for path in sorted(PROFILE_TEMPLATES.iterdir()) if path.is_dir()
        )
        raise ValueError(f"Unknown PROFILE {profile!r}; available profiles: {available}")
    return profile


def owned_profile_service(
    config: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    """Return the one service whose framework artifacts live in this repo."""
    raw_services = config.get("SERVICES")
    if not isinstance(raw_services, dict):
        return None
    local_services = [
        (str(name), service)
        for name, service in raw_services.items()
        if isinstance(service, dict)
        and str(service.get("BUILD_CONTEXT", "")) in {".", "./"}
    ]
    if len(local_services) > 1:
        raise ValueError(
            "At most one service may use BUILD_CONTEXT '.' and own root profile artifacts"
        )
    if config.get("GENERATE_PROFILE_ARTIFACTS", True) is False:
        return None
    return local_services[0] if local_services else None


def owns_profile_artifacts(config: dict[str, Any]) -> bool:
    return owned_profile_service(config) is not None


def selected_templates(config: dict[str, Any]) -> list[tuple[Path, Path]]:
    """Return common, profile, and repository-owned add-on templates."""
    source_roots = [COMMON_TEMPLATES]
    if owns_profile_artifacts(config):
        source_roots.append(PROFILE_TEMPLATES / selected_profile(config))
    selected: list[tuple[Path, Path]] = []
    destinations: set[Path] = set()
    for source_root in source_roots:
        for template in sorted(source_root.rglob("*.tmpl")):
            # This template is rendered twice by the Compose assembler (prod
            # and test); it is not a third operator-facing Compose file.
            if template == COMMON_COMPOSE_TEMPLATE:
                continue
            source_relative = template.relative_to(source_root)
            # Profile Compose and container-installer fragments are internal
            # inputs rendered into common root artifacts, not standalone
            # application files.
            if source_relative.parts[0] in {
                "compose",
                "container_install",
                "documentation",
                "settings_fragments",
            }:
                continue
            relative = destination_for(template, source_root)
            if relative in destinations:
                raise ValueError(
                    f"Template destination {relative} is defined by common and profile files"
                )
            destinations.add(relative)
            selected.append((template, relative))

    # Add-on *.conf templates become editable source configuration in the
    # application repository. The container installer renders those sources
    # into deployment/<addon>/ immediately before Compose validation. Optional
    # assets are repository-owned build inputs copied at their relative paths.
    for addon in normalized_addons(config):
        source_root = ADDON_TEMPLATES / addon / "conf"
        for mode in ("production", "test"):
            template = source_root / f"docker_{mode}_settings.txt.tmpl"
            relative = Path("conf") / addon / f"{addon}_{mode}_settings.txt"
            if relative in destinations:
                raise ValueError(f"Template destination {relative} is duplicated")
            destinations.add(relative)
            selected.append((template, relative))
        for template in sorted(source_root.glob("*.conf.tmpl")):
            relative = Path("conf") / addon / template.name.removesuffix(".tmpl")
            if relative in destinations:
                raise ValueError(f"Template destination {relative} is duplicated")
            destinations.add(relative)
            selected.append((template, relative))
        asset_root = ADDON_TEMPLATES / addon / "assets"
        if asset_root.is_dir():
            for template in sorted(asset_root.rglob("*.tmpl")):
                relative = template.relative_to(asset_root)
                relative = relative.with_name(relative.name.removesuffix(".tmpl"))
                if relative in destinations:
                    raise ValueError(f"Template destination {relative} is duplicated")
                destinations.add(relative)
                selected.append((template, relative))
    return selected


def load_state(target: Path) -> dict:
    state_path = target / STATE_DIR / STATE_FILE
    if not state_path.exists():
        return {"standard_version": None, "files": {}}
    return json.loads(state_path.read_text(encoding="utf-8"))


def write_state(target: Path, config: dict[str, Any], files: dict[str, str]) -> None:
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


def normalized_services(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    raw = config.get("SERVICES")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("SERVICES must be a non-empty JSON object")
    allowed_keys = {
        "PROFILE",
        "BUILD_CONTEXT",
        "DOCKERFILE",
        "IMAGE",
        "INSTALL_CONF",
        "TEST_INSTALL_CONF",
        "PROJECT_MODULE",
        "API",
        "DATABASE",
    }
    services: dict[str, dict[str, str]] = {}
    for raw_name, raw_service in raw.items():
        name = str(raw_name)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise ValueError(f"Invalid service name: {name!r}")
        if not isinstance(raw_service, dict):
            raise ValueError(f"SERVICES.{name} must be a JSON object")
        raw_api = raw_service.get("API", False)
        if not isinstance(raw_api, bool):
            raise ValueError(f"SERVICES.{name}.API must be true or false")
        service = {
            str(key): str(value)
            for key, value in raw_service.items()
            if key not in {"API", "DATABASE"}
        }
        unknown_keys = sorted(service.keys() - allowed_keys)
        if unknown_keys:
            raise ValueError(
                f"SERVICES.{name} contains unsupported keys: "
                + ", ".join(unknown_keys)
            )
        profile = service.get("PROFILE", "").lower()
        if profile not in {"django", "nextjs", "react-vite"}:
            raise ValueError(
                f"SERVICES.{name}.PROFILE must be django, nextjs, or react-vite"
            )
        for required in ("BUILD_CONTEXT", "INSTALL_CONF", "TEST_INSTALL_CONF"):
            if not service.get(required):
                raise ValueError(f"SERVICES.{name}.{required} is required")
        if profile == "django":
            if not service.get("PROJECT_MODULE"):
                raise ValueError(f"SERVICES.{name}.PROJECT_MODULE is required")
        elif "PROJECT_MODULE" in service:
            raise ValueError(
                f"SERVICES.{name}.PROJECT_MODULE is valid only for Django services"
            )
        if raw_api and profile != "django":
            raise ValueError(f"SERVICES.{name}.API is supported only for Django services")
        database = raw_service.get("DATABASE", "external")
        if database not in {"external", "compose"}:
            raise ValueError(
                f"SERVICES.{name}.DATABASE must be external or compose"
            )
        if "DATABASE" in raw_service and profile != "django":
            raise ValueError(
                f"SERVICES.{name}.DATABASE is supported only for Django services"
            )
        service["API"] = "true" if raw_api else "false"
        service["DATABASE"] = str(database)
        service["PROFILE"] = profile
        service.setdefault("IMAGE", f"{name.replace('_', '-')}:local")
        service.setdefault("DOCKERFILE", "Dockerfile")
        services[name] = service
    owned_names = [
        name
        for name, service in services.items()
        if service["BUILD_CONTEXT"] in {".", "./"}
    ]
    ordered_names = owned_names + sorted(set(services) - set(owned_names))
    return {name: services[name] for name in ordered_names}


def normalized_addons(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    services = normalized_services(config)
    default_config_service = next(iter(services))
    raw = config.get("ADDONS", {})
    if isinstance(raw, str):
        raw = {name.strip(): {} for name in raw.split(",") if name.strip()}
    elif isinstance(raw, list):
        raw = {str(name): {} for name in raw}
    if not isinstance(raw, dict):
        raise ValueError("ADDONS must be an object, list, or comma-separated string")
    addons: dict[str, dict[str, Any]] = {}
    available_addons = {
        path.name for path in ADDON_TEMPLATES.iterdir() if path.is_dir()
    }
    for raw_name, options in raw.items():
        name = str(raw_name).lower()
        if name not in available_addons:
            available = ", ".join(sorted(available_addons))
            raise ValueError(
                f"Unsupported add-on {name!r}; available add-ons: {available}"
            )
        if options is None:
            options = {}
        if not isinstance(options, dict):
            raise ValueError(f"ADDONS.{name} must be a JSON object")
        normalized_options = dict(options)
        supported_options = {"CONFIG_SERVICE", "MOUNTS", "MODES"}
        if name == "keycloak":
            supported_options.update({"ADMIN_ACCESS", "OIDC_SERVICES"})
        unknown_options = sorted(set(normalized_options) - supported_options)
        if unknown_options:
            raise ValueError(
                f"ADDONS.{name} contains unsupported options: "
                + ", ".join(unknown_options)
            )
        config_service = str(
            normalized_options.get("CONFIG_SERVICE", default_config_service)
        )
        if config_service not in services:
            raise ValueError(
                f"ADDONS.{name}.CONFIG_SERVICE targets unknown application "
                f"service {config_service!r}"
            )
        normalized_options["CONFIG_SERVICE"] = config_service
        if name == "keycloak":
            default_oidc_services = (
                [config_service]
                if services[config_service]["PROFILE"] == "django"
                else []
            )
            raw_oidc_services = normalized_options.get(
                "OIDC_SERVICES", default_oidc_services
            )
            if not isinstance(raw_oidc_services, list):
                raise ValueError("ADDONS.keycloak.OIDC_SERVICES must be an array")
            oidc_services = list(dict.fromkeys(map(str, raw_oidc_services)))
            unknown_oidc_services = sorted(set(oidc_services) - set(services))
            if unknown_oidc_services:
                raise ValueError(
                    "ADDONS.keycloak.OIDC_SERVICES targets unknown application "
                    "services: " + ", ".join(unknown_oidc_services)
                )
            non_django_oidc_services = [
                service_name
                for service_name in oidc_services
                if services[service_name]["PROFILE"] != "django"
            ]
            if non_django_oidc_services:
                raise ValueError(
                    "ADDONS.keycloak.OIDC_SERVICES currently supports only Django "
                    "services: " + ", ".join(non_django_oidc_services)
                )
            normalized_options["OIDC_SERVICES"] = oidc_services
            admin_access = normalized_options.get("ADMIN_ACCESS", False)
            if not isinstance(admin_access, bool):
                raise ValueError("ADDONS.keycloak.ADMIN_ACCESS must be a boolean")
            normalized_options["ADMIN_ACCESS"] = admin_access
        raw_modes = normalized_options.get("MODES", ["prod", "test"])
        if not isinstance(raw_modes, list) or not raw_modes:
            raise ValueError(f"ADDONS.{name}.MODES must be a non-empty array")
        mode_aliases = {"prod": "prod", "production": "prod", "test": "test"}
        requested_modes = [str(mode).lower() for mode in raw_modes]
        invalid_modes = sorted(set(requested_modes) - set(mode_aliases))
        if invalid_modes:
            raise ValueError(
                f"ADDONS.{name}.MODES contains unsupported modes: "
                + ", ".join(invalid_modes)
            )
        normalized_options["MODES"] = list(
            dict.fromkeys(mode_aliases[mode] for mode in requested_modes)
        )
        addons[name] = normalized_options
    return addons


def rendered_addon_settings(config: dict[str, Any], addon: str, mode: str) -> str:
    """Render one add-on-owned settings fragment from its source template."""
    template = (
        ADDON_TEMPLATES
        / addon
        / "conf"
        / f"docker_{mode}_settings.txt.tmpl"
    )
    if not template.is_file():
        raise ValueError(f"Missing {addon} {mode} settings template: {template}")
    values = scalar_values(config)
    values.setdefault("APP_SLUG", "application")
    return render(template, values).decode().rstrip("\n")


def rendered_addon_settings_documentation(
    config: dict[str, Any], addon: str
) -> str:
    """Render the settings guidance owned by one infrastructure add-on."""
    template = ADDON_TEMPLATES / addon / "conf" / "INSTALL_SETTINGS.md.tmpl"
    if not template.is_file():
        raise ValueError(f"Missing {addon} settings documentation: {template}")
    values = scalar_values(config)
    values.setdefault("APP_SLUG", "application")
    return render(template, values).decode().rstrip("\n")


def addon_setting_keys(config: dict[str, Any], addon: str) -> list[str]:
    """Discover the add-on environment contract from both settings templates."""
    keys: list[str] = []
    for mode in ("production", "test"):
        fragment = rendered_addon_settings(config, addon, mode)
        for key in re.findall(r"^([A-Z][A-Z0-9_]*)[ \t]*=", fragment, re.MULTILINE):
            if key not in keys:
                keys.append(key)
    return keys


def addon_settings_section(
    config: dict[str, Any], service_name: str, mode: str
) -> str:
    """Keep application settings free of independently mapped add-on values."""
    return "# Infrastructure add-ons use files below conf/<addon>/."


def rendered_profile_callback(
    profile: str,
    callback: str,
    values: dict[str, str],
    *,
    required: bool = False,
) -> list[str]:
    """Render an optional framework-owned container installer callback."""
    template = (
        PROFILE_TEMPLATES
        / profile
        / "container_install"
        / f"{callback}.sh.tmpl"
    )
    if not template.is_file():
        if not required:
            return []
        raise ValueError(f"Missing {profile} container callback template: {template}")
    return render(template, values).decode().rstrip("\n").splitlines()


def rendered_addon_callback(
    addon: str,
    callback: str,
    values: dict[str, str],
    *,
    required: bool = False,
) -> list[str]:
    """Render an optional add-on-owned container installer callback."""
    template = (
        ADDON_TEMPLATES
        / addon
        / "container_install"
        / f"{callback}.sh.tmpl"
    )
    if not template.is_file():
        if not required:
            return []
        raise ValueError(f"Missing {addon} container callback template: {template}")
    return render(template, values).decode().rstrip("\n").splitlines()


def rendered_addon_compose_fragment(
    addon: str,
    fragment: str,
    values: dict[str, str],
    *,
    required: bool = True,
) -> list[str]:
    """Render one repeatable add-on-owned Compose fragment."""
    template = ADDON_TEMPLATES / addon / "compose" / f"{fragment}.yml.tmpl"
    if not template.is_file():
        if not required:
            return []
        raise ValueError(f"Missing {addon} Compose fragment: {template}")
    return render(template, values).decode().rstrip("\n").splitlines()


def addon_settings_documentation(config: dict[str, Any]) -> str:
    """Document every add-on whose settings are generated in this repository."""
    sections = [
        rendered_addon_settings_documentation(config, addon)
        for addon in normalized_addons(config)
    ]
    return "\n\n".join(sections) or "No infrastructure add-on settings are owned by this service."


def env_prefix(service_name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", service_name.upper())


def compose_variable(prefix: str, key: str, default: str | None = None) -> str:
    name = f"{prefix}_{key}"
    if default is None:
        return f"${{{name}:?{name} is required}}"
    return f"${{{name}:-{default}}}"


# =============================================================================
# PROFILE COMPILERS
# =============================================================================
# Profile compilers may select and repeat profile-owned template fragments from
# project.json topology. Do not put framework YAML, runtime defaults, shell
# commands, permission policy, or documentation here; those belong under
# scaffold/templates/profiles/<profile>/.
#
# compose_service_block is deliberately profile-neutral. Add profile-specific
# Python below this heading only when validation/iteration cannot be represented
# by the profile's conventional Compose fragments.


def optional_django_install_settings(
    service: dict[str, str], mode: str, has_oidc: bool, has_keycloak_admin: bool
) -> str:
    """Render optional API/OIDC installation values for one Django service."""
    if service["PROFILE"] != "django":
        return ""
    fragments: list[str] = []
    if service.get("API") == "true":
        fragments.append(
            (
                PROFILE_TEMPLATES
                / "django"
                / "settings_fragments"
                / f"api_{mode}_settings.txt.tmpl"
            ).read_text(encoding="utf-8").rstrip()
        )
    if has_oidc:
        fragments.append(
            (
                ADDON_TEMPLATES
                / "keycloak"
                / "conf"
                / f"application_{mode}_settings.txt.tmpl"
            ).read_text(encoding="utf-8").rstrip()
        )
    if has_keycloak_admin:
        fragments.append(
            (
                ADDON_TEMPLATES
                / "keycloak"
                / "conf"
                / f"admin_application_{mode}_settings.txt.tmpl"
            ).read_text(encoding="utf-8").rstrip()
        )
    return "\n\n".join(fragments)


def optional_django_python_settings(
    service: dict[str, str], has_oidc: bool, has_keycloak_admin: bool
) -> str:
    """Render optional environment readers into the Django settings template."""
    if service["PROFILE"] != "django":
        return ""
    fragments: list[str] = []
    if service.get("API") == "true":
        fragments.append(
            (PROFILE_TEMPLATES / "django" / "settings_fragments" / "api_settings.py.tmpl")
            .read_text(encoding="utf-8")
            .rstrip()
        )
    if has_oidc:
        fragments.append(
            (ADDON_TEMPLATES / "keycloak" / "conf" / "application_settings.py.tmpl")
            .read_text(encoding="utf-8")
            .rstrip()
        )
    if has_keycloak_admin:
        fragments.append(
            (ADDON_TEMPLATES / "keycloak" / "conf" / "admin_application_settings.py.tmpl")
            .read_text(encoding="utf-8")
            .rstrip()
        )
    return "\n\n".join(fragments)


def optional_django_compose_environment(
    service: dict[str, str],
    mode: str,
    has_oidc: bool,
    has_keycloak_admin: bool,
    app_slug: str,
) -> str:
    """Render optional API/OIDC variables into a Django Compose service."""
    if service["PROFILE"] != "django":
        return ""
    fragments: list[str] = []
    values = {"ENV_PREFIX": "{{ENV_PREFIX}}", "APP_SLUG": app_slug}
    if service.get("API") == "true":
        fragments.append(
            render(
                PROFILE_TEMPLATES
                / "django"
                / "compose"
                / "api-service-environment.yml.tmpl",
                values,
            ).decode().rstrip()
        )
    if has_oidc:
        fragments.append(
            render(
                ADDON_TEMPLATES
                / "keycloak"
                / "compose"
                / f"application-{mode}-environment.yml.tmpl",
                values,
            ).decode().rstrip()
        )
    if has_keycloak_admin:
        fragments.append(
            render(
                ADDON_TEMPLATES
                / "keycloak"
                / "compose"
                / f"admin-application-{mode}-environment.yml.tmpl",
                values,
            ).decode().rstrip()
        )
    return ("\n" + "\n".join(fragments)) if fragments else ""


def compose_service_block(
    name: str,
    service: dict[str, str],
    mode: str,
    oidc_services: set[str],
    keycloak_config_service: str | None,
    keycloak_admin_access: bool,
    app_slug: str,
) -> ComposeCompilation:
    """Compile one service and optional profile-owned Compose fragments."""
    prefix = env_prefix(name)
    profile = service["PROFILE"]
    compose_templates = PROFILE_TEMPLATES / profile / "compose"
    template = compose_templates / f"{mode}.service.yml.tmpl"
    if not template.is_file():
        raise ValueError(
            f"Missing {profile} {mode} Compose service template: {template}"
        )
    values = {
        "SERVICE_NAME": name,
        "ENV_PREFIX": prefix,
        "IMAGE_NAME": service["IMAGE"],
        "BUILD_CONTEXT_JSON": json.dumps(service["BUILD_CONTEXT"]),
        "DOCKERFILE_JSON": json.dumps(service["DOCKERFILE"]),
        "PROJECT_MODULE": service.get("PROJECT_MODULE", ""),
        "DATABASE_DEPENDS_ON": (
            "    depends_on:\n"
            f"      {name}-db:\n"
            "        condition: service_healthy"
            if mode == "prod" and service["DATABASE"] == "compose"
            else ""
        ),
        "OPTIONAL_SERVICE_ENVIRONMENT": optional_django_compose_environment(
            service,
            mode,
            name in oidc_services,
            name == keycloak_config_service and keycloak_admin_access,
            app_slug,
        ).replace("{{ENV_PREFIX}}", prefix),
    }

    def optional_fragment(kind: str) -> list[str]:
        fragment = compose_templates / f"{mode}.{kind}.yml.tmpl"
        if not fragment.is_file():
            return []
        return render(fragment, values).decode().rstrip("\n").splitlines()

    lines = render(template, values).decode().rstrip("\n").splitlines()
    return ComposeCompilation(
        service_lines=lines,
        support_lines=(
            optional_fragment("support-services")
            if mode != "prod" or service["DATABASE"] == "compose"
            else []
        ),
        volume_lines=(
            optional_fragment("volumes")
            + (
                optional_fragment("database-volumes")
                if mode == "prod" and service["DATABASE"] == "compose"
                else []
            )
        ),
        secret_lines=optional_fragment("secrets"),
        artifacts=[],
    )


# =============================================================================
# GENERIC ADD-ON COMPILER
# =============================================================================
# Add-ons own their Compose YAML and declare optional per-service/profile
# fragments by filename. The compiler only repeats and merges those fragments;
# it contains no Apache, Keycloak, framework, or runtime configuration policy.


def addon_dependency_services(addon: str, values: dict[str, str]) -> list[str]:
    """Read healthy service names another add-on may depend upon."""
    path = ADDON_TEMPLATES / addon / "compose" / "dependency-services.txt.tmpl"
    if not path.is_file():
        return []
    names = [
        line.strip()
        for line in render(path, values).decode().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    for name in names:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", name):
            raise ValueError(f"Invalid dependency service {name!r} in {path}")
    return names


def compile_addon_compose(
    addon: str,
    config: dict[str, Any],
    services: dict[str, dict[str, str]],
    addons: dict[str, dict[str, Any]],
    mode: str,
) -> ComposeCompilation:
    """Compile one add-on entirely from conventional template fragments."""
    options = addons[addon]
    if mode not in options["MODES"]:
        return ComposeCompilation([], [], [], [], [])
    dependency_names = list(services)
    for selected_addon in addons:
        if selected_addon != addon and mode in addons[selected_addon]["MODES"]:
            dependency_names.extend(
                addon_dependency_services(selected_addon, scalar_values(config))
            )
    depends_on = "\n".join(
        f"      {name}:\n        condition: service_healthy"
        for name in dict.fromkeys(dependency_names)
    )

    environment_lines: list[str] = []
    application_mounts: list[str] = []
    for name, service in services.items():
        fragment_values = {
            **service,
            "SERVICE_NAME": name,
            "ENV_PREFIX": env_prefix(name),
        }
        environment_lines += rendered_addon_compose_fragment(
            addon, "service-environment", fragment_values, required=False
        )
        environment_lines += rendered_addon_compose_fragment(
            addon,
            f"{service['PROFILE']}-service-environment",
            fragment_values,
            required=False,
        )
        application_mounts += rendered_addon_compose_fragment(
            addon,
            f"{service['PROFILE']}-{mode}-mounts",
            fragment_values,
            required=False,
        )

    optional_mounts = options.get("MOUNTS", [])
    if not isinstance(optional_mounts, list):
        raise ValueError(f"ADDONS.{addon}.MOUNTS must be a JSON array")
    for mount in optional_mounts:
        application_mounts += rendered_addon_compose_fragment(
            addon, "application-mount", {"MOUNT": str(mount)}, required=False
        )

    service_volumes = rendered_addon_compose_fragment(
        addon, f"{mode}.service-volumes", {}, required=False
    )
    values = {
        **scalar_values(config),
        "ADDON_DEPENDS_ON": depends_on,
        "ADDON_SERVICE_ENVIRONMENT": "\n".join(environment_lines),
        "ADDON_SERVICE_VOLUMES": "\n".join(service_volumes),
        "ADDON_APPLICATION_MOUNTS": "\n".join(application_mounts),
    }
    service_template = ADDON_TEMPLATES / addon / "compose" / f"{mode}.service.yml.tmpl"
    service_lines = render(service_template, values).decode().rstrip("\n").splitlines()
    return ComposeCompilation(
        service_lines=service_lines,
        support_lines=rendered_addon_compose_fragment(
            addon, f"{mode}.support-services", values, required=False
        ),
        volume_lines=rendered_addon_compose_fragment(
            addon, f"{mode}.volumes", values, required=False
        ),
        secret_lines=rendered_addon_compose_fragment(
            addon, f"{mode}.secrets", values, required=False
        ),
        artifacts=[],
    )


# =============================================================================
# COMPOSE AND ARTIFACT ASSEMBLY
# =============================================================================
# Code below this boundary coordinates profile/add-on fragments and final output.
# Add-on dispatch may occur here, but reusable add-on-specific validation and
# iteration must be named and placed in its compiler section above. Configuration
# syntax and runtime defaults always remain in the owning templates.


def compose_document(config: dict[str, Any], mode: str) -> tuple[bytes, list[tuple[Path, bytes]]]:
    services = normalized_services(config)
    addons = normalized_addons(config)
    keycloak_config_service = None
    oidc_services: set[str] = set()
    if "keycloak" in addons:
        keycloak_config_service = str(addons["keycloak"]["CONFIG_SERVICE"])
        oidc_services = set(addons["keycloak"]["OIDC_SERVICES"])
    keycloak_admin_access = bool(
        "keycloak" in addons and addons["keycloak"].get("ADMIN_ACCESS", False)
    )
    compilations = [
        compose_service_block(
            name,
            service,
            mode,
            oidc_services,
            keycloak_config_service,
            keycloak_admin_access,
            str(config["APP_SLUG"]),
        )
        for name, service in services.items()
    ]
    compilations += [
        compile_addon_compose(name, config, services, addons, mode)
        for name in addons
    ]

    service_lines = [
        line for compilation in compilations for line in compilation.service_lines
    ]
    support_lines = [
        line for compilation in compilations for line in compilation.support_lines
    ]
    volume_lines = [
        line for compilation in compilations for line in compilation.volume_lines
    ]
    secret_lines = [
        line for compilation in compilations for line in compilation.secret_lines
    ]
    artifacts = [
        artifact for compilation in compilations for artifact in compilation.artifacts
    ]

    service_blocks = "\n".join(service_lines + support_lines)
    volume_section = ""
    if volume_lines:
        volume_section = "\nvolumes:\n" + "\n".join(dict.fromkeys(volume_lines))
    secret_section = ""
    if secret_lines:
        secret_section = "\nsecrets:\n" + "\n".join(secret_lines)
    document_template = COMMON_COMPOSE_TEMPLATE
    document = render(
        document_template,
        {
            "COMPOSE_SERVICE_BLOCKS": service_blocks,
            "COMPOSE_VOLUMES_SECTION": volume_section,
            "COMPOSE_SECRETS_SECTION": secret_section,
        },
    )
    return document.rstrip(b"\n") + b"\n", artifacts


def orchestrator_artifacts(config: dict[str, Any]) -> list[tuple[Path, bytes]]:
    normalized_services(config)
    normalized_addons(config)
    prod, prod_extra = compose_document(config, "prod")
    test, test_extra = compose_document(config, "test")
    artifacts = [
        (Path("docker-compose.prod.yml"), prod),
        (Path("docker-compose.test.yml"), test),
        *prod_extra,
        *test_extra,
    ]
    unique: dict[Path, bytes] = {}
    for path, content in artifacts:
        if path in unique and unique[path] != content:
            raise ValueError(f"Generated artifact {path} differs between modes")
        unique[path] = content
    return list(unique.items())


def bash_array(values: list[str]) -> str:
    return "(" + " ".join(shlex.quote(value) for value in values) + ")"


def rendered_documentation_fragment(
    owner: str, name: str, fragment: str, values: dict[str, str]
) -> str:
    """Render one common, profile, or add-on-owned documentation fragment."""
    if owner == "common":
        template = COMMON_TEMPLATES / "documentation" / f"{fragment}.tmpl"
    elif owner == "profile":
        template = PROFILE_TEMPLATES / name / "documentation" / f"{fragment}.tmpl"
    elif owner == "addon":
        template = ADDON_TEMPLATES / name / "documentation" / f"{fragment}.tmpl"
    else:
        raise ValueError(f"Unsupported documentation owner: {owner}")
    if not template.is_file():
        raise ValueError(f"Missing {owner} documentation fragment: {template}")
    return render(template, values).decode().rstrip("\n")


def documentation_template_values(config: dict[str, Any]) -> dict[str, str]:
    """Render and combine documentation fragments selected by project topology."""
    services = normalized_services(config)
    addons = normalized_addons(config)
    service_rows: list[str] = []
    persistence_rows: list[str] = []
    config_map_examples: list[str] = []
    config_copy_commands: list[str] = []
    protected_settings_paths: list[str] = []
    post_install_checks: list[str] = []
    host_path_preparation_commands: list[str] = []
    selected_profiles = list(
        dict.fromkeys(service["PROFILE"] for service in services.values())
    )
    owned = owned_profile_service(config)
    primary_service = owned[0] if owned else next(iter(services))

    for name, service in services.items():
        service_rows.append(
            rendered_documentation_fragment(
                "common",
                "",
                "service-inventory-row.md",
                {
                    "SERVICE_NAME": name,
                    "PROFILE": service["PROFILE"],
                    "BUILD_CONTEXT": service["BUILD_CONTEXT"],
                },
            )
        )
        config_map_examples.append(
            rendered_documentation_fragment(
                "common",
                "",
                "config-map-example.txt",
                {"SERVICE_NAME": name},
            )
        )
        config_copy_commands.append(
            f"install -m 0600 {shlex.quote(service['INSTALL_CONF'])} "
            f"deployment/settings/{name}_production_settings.txt"
        )
        protected_settings_paths.append(
            f"deployment/settings/{name}_production_settings.txt"
        )
        if service["PROFILE"] == "django":
            protected_settings = (
                f"deployment/settings/{name}_production_settings.txt"
            )
            host_path_preparation_commands.extend(
                [
                    "(",
                    f"  source {shlex.quote(protected_settings)}",
                    f'  : "${{HOST_LOG_PATH:?HOST_LOG_PATH is required for {name}}}"',
                    f'  : "${{DJANGO_SETTINGS_PATH:?DJANGO_SETTINGS_PATH is required for {name}}}"',
                    '  sudo install -d -o "$PODMAN_USER" -g "$PODMAN_USER" \\',
                    '    "$HOST_LOG_PATH" "$(dirname "$DJANGO_SETTINGS_PATH")"',
                    ")",
                ]
            )
        post_install_checks.append(
            f"- `{name}`: confirmar su endpoint `/health/` y un flujo "
            "representativo de lectura."
        )
        if service.get("API") == "true":
            post_install_checks.append(
                f"- API de `{name}`: confirmar la ruta documentada con "
                "autenticacion valida y el rechazo de credenciales ausentes o "
                "invalidas."
            )
        persistence_rows.append(
            rendered_documentation_fragment(
                "profile",
                service["PROFILE"],
                (
                    "compose-persistence-rows.md"
                    if service["DATABASE"] == "compose"
                    else "persistence-rows.md"
                ),
                {"SERVICE_NAME": name, "APP_SLUG": str(config["APP_SLUG"])},
            )
        )
    for addon in addons:
        config_map_examples.append(
            rendered_documentation_fragment(
                "common",
                "",
                "config-map-example.txt",
                {"SERVICE_NAME": addon},
            )
        )
        config_copy_commands.append(
            f"install -m 0600 conf/{addon}/{addon}_production_settings.txt "
            f"deployment/settings/{addon}_production_settings.txt"
        )
        protected_settings_paths.append(
            f"deployment/settings/{addon}_production_settings.txt"
        )
        addon_host_paths = {
            "apache": ("APACHE_LOG_PATH",),
            "keycloak": ("KEYCLOAK_IMPORT_PATH",),
        }.get(addon, ())
        if addon_host_paths:
            protected_settings = (
                f"deployment/settings/{addon}_production_settings.txt"
            )
            host_path_preparation_commands.extend(
                ["(", f"  source {shlex.quote(protected_settings)}"]
            )
            for variable in addon_host_paths:
                host_path_preparation_commands.append(
                    f'  : "${{{variable}:?{variable} is required for {addon}}}"'
                )
            quoted_paths = " ".join(f'"${variable}"' for variable in addon_host_paths)
            host_path_preparation_commands.extend(
                [
                    '  sudo install -d -o "$PODMAN_USER" -g "$PODMAN_USER" \\',
                    f"    {quoted_paths}",
                    ")",
                ]
            )

    addon_post_install_checks = {
        "apache": (
            "- Apache: confirmar la URL publica registrada, DNS/TLS, proxy, "
            "cabeceras reenviadas y el endpoint restringido de server-status."
        ),
        "keycloak": (
            "- Keycloak: confirmar discovery del realm, validacion de tokens "
            "OIDC y login/logout; probar acceso administrativo solo cuando el "
            "add-on lo habilite."
        ),
        "nextstrain": (
            "- Nextstrain: confirmar la ruta publica y cada dataset o narrativa "
            "esperados tras cargar los datos Auspice revisados."
        ),
        "samba": (
            "- Samba: en cada modo habilitado, confirmar acceso autenticado y un "
            "flujo representativo de lectura/escritura desde un cliente aprobado."
        ),
    }
    post_install_checks.extend(
        addon_post_install_checks[addon]
        for addon in addons
        if addon in addon_post_install_checks
    )

    config_backup_commands = ['cp .env.production.file "$BACKUP_DIR/"']
    config_backup_commands.extend(
        f"cp {shlex.quote(path)} \"$BACKUP_DIR/\""
        for path in protected_settings_paths
    )
    config_restore_commands = [
        f"install -m 0600 \"$BACKUP_DIR/{Path(path).name}\" {shlex.quote(path)}"
        for path in protected_settings_paths
    ]

    profile_notes = [
        rendered_documentation_fragment("profile", profile, "profile.md", {})
        for profile in selected_profiles
    ]
    bare_metal_notes = [
        rendered_documentation_fragment(
            "profile", profile, "bare-metal.md", {"PRIMARY_SERVICE": primary_service}
        )
        for profile in selected_profiles
    ]
    local_test_notes = [
        rendered_documentation_fragment(
            "profile", profile, "local-test.md", {}
        )
        for profile in selected_profiles
        if (PROFILE_TEMPLATES / profile / "documentation" / "local-test.md.tmpl").is_file()
    ]
    migration_notes = [
        rendered_documentation_fragment(
            "profile", profile, "migrations.md", {}
        )
        for profile in selected_profiles
        if (PROFILE_TEMPLATES / profile / "documentation" / "migrations.md.tmpl").is_file()
    ]
    operational_notes: list[str] = []
    runbook_operational_notes: list[str] = []
    addon_backup_commands: list[str] = []
    addon_restore_commands: list[str] = []
    for name, service in services.items():
        operational = (
            PROFILE_TEMPLATES
            / service["PROFILE"]
            / "documentation"
            / "operations.md.tmpl"
        )
        if operational.is_file():
            operational_notes.append(
                rendered_documentation_fragment(
                    "profile",
                    service["PROFILE"],
                    "operations.md",
                    {"SERVICE_NAME": name},
                )
            )
        runbook_operational = (
            PROFILE_TEMPLATES
            / service["PROFILE"]
            / "documentation"
            / "operations-leame.md.tmpl"
        )
        if runbook_operational.is_file():
            runbook_operational_notes.append(
                rendered_documentation_fragment(
                    "profile",
                    service["PROFILE"],
                    "operations-leame.md",
                    {"SERVICE_NAME": name},
                )
            )
    addon_notes = [
        rendered_documentation_fragment("addon", addon, "addon.md", {})
        for addon in addons
    ]
    for addon in addons:
        addon_backup = ADDON_TEMPLATES / addon / "documentation" / "backup.md.tmpl"
        if addon_backup.is_file():
            addon_backup_commands.append(
                rendered_documentation_fragment(
                    "addon",
                    addon,
                    "backup.md",
                    {"APP_SLUG": str(config["APP_SLUG"])},
                )
            )
        addon_restore = ADDON_TEMPLATES / addon / "documentation" / "restore.md.tmpl"
        if addon_restore.is_file():
            addon_restore_commands.append(
                rendered_documentation_fragment(
                    "addon",
                    addon,
                    "restore.md",
                    {"APP_SLUG": str(config["APP_SLUG"])},
                )
            )
        addon_local_test = ADDON_TEMPLATES / addon / "documentation" / "local-test.md.tmpl"
        if addon_local_test.is_file():
            local_test_notes.append(
                rendered_documentation_fragment("addon", addon, "local-test.md", {})
            )
        addon_operations = ADDON_TEMPLATES / addon / "documentation" / "operations.md.tmpl"
        if addon_operations.is_file():
            operational_notes.append(
                rendered_documentation_fragment(
                    "addon",
                    addon,
                    "operations.md",
                    {
                        "APP_SLUG": str(config["APP_SLUG"]),
                        "CONFIG_MAP_EXAMPLES": " ".join(config_map_examples),
                    },
                )
            )
        addon_runbook_operations = (
            ADDON_TEMPLATES / addon / "documentation" / "operations-leame.md.tmpl"
        )
        if addon_runbook_operations.is_file():
            runbook_operational_notes.append(
                rendered_documentation_fragment(
                    "addon",
                    addon,
                    "operations-leame.md",
                    {
                        "APP_SLUG": str(config["APP_SLUG"]),
                        "CONFIG_MAP_EXAMPLES": " ".join(config_map_examples),
                    },
                )
            )
        addon_bare_metal = ADDON_TEMPLATES / addon / "documentation" / "bare-metal.md.tmpl"
        if addon_bare_metal.is_file():
            bare_metal_notes.append(
                rendered_documentation_fragment(
                    "addon",
                    addon,
                    "bare-metal.md",
                    {"APP_SLUG": str(config["APP_SLUG"])},
                )
            )
        persistence = ADDON_TEMPLATES / addon / "documentation" / "persistence-rows.md.tmpl"
        if persistence.is_file():
            persistence_rows.append(
                rendered_documentation_fragment(
                    "addon",
                    addon,
                    "persistence-rows.md",
                    {"APP_SLUG": str(config["APP_SLUG"])},
                )
            )
    if not addon_notes:
        addon_notes.append(
            rendered_documentation_fragment("common", "", "no-addons.md", {})
        )

    return {
        "REPOSITORY_URL": str(config.get("REPOSITORY_URL", "<repository-url>")),
        "SERVICE_INVENTORY_ROWS": "\n".join(service_rows),
        "PROFILE_DOCUMENTATION": "\n".join(profile_notes),
        "LOCAL_TEST_DOCUMENTATION": "\n\n".join(local_test_notes),
        "BARE_METAL_DOCUMENTATION": "\n\n".join(bare_metal_notes),
        "MIGRATION_DOCUMENTATION": "\n\n".join(migration_notes),
        "OPERATIONAL_DOCUMENTATION": "\n\n".join(operational_notes),
        "RUNBOOK_OPERATIONAL_DOCUMENTATION": "\n\n".join(
            runbook_operational_notes
        ),
        "ADDON_DOCUMENTATION": "\n".join(addon_notes),
        "PERSISTENCE_ROWS": "\n".join(persistence_rows),
        "CONFIG_MAP_EXAMPLES": " ".join(config_map_examples),
        "CONFIG_COPY_COMMANDS": "\n".join(config_copy_commands),
        "CONFIG_BACKUP_COMMANDS": "\n".join(config_backup_commands),
        "CONFIG_RESTORE_COMMANDS": "\n".join(config_restore_commands),
        "POST_INSTALL_CHECKS": "\n".join(post_install_checks),
        "HOST_PATH_PREPARATION_COMMANDS": "\n".join(
            host_path_preparation_commands
        ),
        "ADDON_BACKUP_COMMANDS": "\n".join(addon_backup_commands),
        "ADDON_RESTORE_COMMANDS": "\n".join(addon_restore_commands),
    }


def settings_template_values(config: dict[str, Any]) -> dict[str, str]:
    """Build only profile-settings sections and their add-on documentation."""
    services = normalized_services(config)
    owned = owned_profile_service(config)
    settings_owner = owned[0] if owned else next(iter(services))
    owner_service = services[settings_owner]
    addons = normalized_addons(config)
    has_oidc = bool(
        "keycloak" in addons
        and settings_owner in addons["keycloak"]["OIDC_SERVICES"]
    )
    has_keycloak_admin = bool(
        has_oidc and addons["keycloak"].get("ADMIN_ACCESS", False)
    )
    return {
        "PRODUCTION_ADDON_SETTINGS": addon_settings_section(
            config, settings_owner, "production"
        ),
        "TEST_ADDON_SETTINGS": addon_settings_section(config, settings_owner, "test"),
        "ADDON_SETTINGS_DOCUMENTATION": addon_settings_documentation(config),
        "PRODUCTION_OPTIONAL_APP_SETTINGS": optional_django_install_settings(
            owner_service, "production", has_oidc, has_keycloak_admin
        ),
        "TEST_OPTIONAL_APP_SETTINGS": optional_django_install_settings(
            owner_service, "test", has_oidc, has_keycloak_admin
        ),
        "DJANGO_OPTIONAL_SETTINGS": optional_django_python_settings(
            owner_service, has_oidc, has_keycloak_admin
        ),
    }


def service_container_installer_compilation(
    services: dict[str, dict[str, str]],
) -> ContainerInstallerCompilation:
    """Compile application-neutral mappings declared by every service."""
    result = ContainerInstallerCompilation()
    result.install_services.extend(services)
    result.permission_services.extend(services)
    result.configured_services.extend(services)
    result.deployment_values.append('        "GIT_REVISION|$git_revision"')
    for name, service in services.items():
        prefix = env_prefix(name)
        result.default_conf_cases.append(
            f"        {name}) [ \"$mode\" = test ] && echo "
            f"{shlex.quote(service['TEST_INSTALL_CONF'])} || echo "
            f"{shlex.quote(service['INSTALL_CONF'])} ;;"
        )
        result.build_context_cases.append(
            f"        {name}) echo {shlex.quote(service['BUILD_CONTEXT'])} ;;"
        )
        result.image_cases.append(
            f"        {name}) echo {shlex.quote(service['IMAGE'])} ;;"
        )
        result.profile_cases.append(f"        {name}) echo {service['PROFILE']} ;;")
        result.dockerfile_cases.append(
            f"        {name}) echo {shlex.quote(service['DOCKERFILE'])} ;;"
        )
        result.settings_sources.append(
            f'        "{prefix}|${{install_conf_host_by_service[{name}]}}"'
        )
        result.deployment_values.append(
            f'        "{prefix}_IMAGE|{service["IMAGE"]}"'
        )
    return result


def profile_container_installer_compilation(
    services: dict[str, dict[str, str]],
) -> ContainerInstallerCompilation:
    """Compile callbacks owned by each service's selected framework profile."""
    result = ContainerInstallerCompilation()
    callback_targets = {
        "readiness-path.case": result.readiness_cases,
        "container-install-conf.case": result.container_conf_cases,
        "create-host-bind-sources": result.host_sources,
        "set-host-bind-permissions": result.host_permissions,
        "running-permissions.case": result.running_cases,
        "bootstrap.case": result.bootstrap_cases,
        "production-build.case": result.production_build_cases,
    }
    for name, service in services.items():
        callback_values = {
            **service,
            "SERVICE_NAME": name,
            "SERVICE_NAME_SHELL": shlex.quote(name),
            "SPEC_NAME": re.sub(r"[^a-zA-Z0-9_]", "_", name),
            "BUILD_CONTEXT_SHELL": shlex.quote(service["BUILD_CONTEXT"]),
        }
        for callback, target in callback_targets.items():
            target.extend(
                rendered_profile_callback(
                    service["PROFILE"], callback, callback_values
                )
            )
    return result


def addon_container_services(
    addon: str, filename: str, values: dict[str, str]
) -> list[str]:
    """Read container service names declared by an add-on lifecycle file."""
    template = (
        ADDON_TEMPLATES
        / addon
        / "container_install"
        / filename
    )
    if not template.is_file():
        return []
    names = [
        line.strip()
        for line in render(template, values).decode().splitlines()
    ]
    names = [name for name in names if name and not name.startswith("#")]
    for name in names:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", name):
            raise ValueError(f"Invalid container service {name!r} in {template}")
    return names


def addon_container_installer_compilation(
    config: dict[str, Any], addons: dict[str, dict[str, Any]]
) -> ContainerInstallerCompilation:
    """Compile callbacks and settings exports owned by selected add-ons."""
    result = ContainerInstallerCompilation()
    callback_targets = {
        "create-host-bind-sources": result.host_sources,
        "set-host-bind-permissions": result.host_permissions,
        "running-permissions.case": result.running_cases,
    }
    for addon, options in addons.items():
        config_service = str(options["CONFIG_SERVICE"])
        callback_values = {
            **scalar_values(config),
            "CONFIG_SERVICE": config_service,
            "CONFIG_SERVICE_SHELL": shlex.quote(config_service),
        }
        result.addon_build_services.extend(
            addon_container_services(addon, "build-services.txt.tmpl", callback_values)
        )
        result.permission_services.extend(
            addon_container_services(
                addon, "permission-services.txt.tmpl", callback_values
            )
        )
        result.configured_services.append(addon)
        result.default_conf_cases.append(
            f"        {addon}) [ \"$mode\" = test ] && echo "
            f"conf/{addon}/{addon}_test_settings.txt || echo "
            f"conf/{addon}/{addon}_production_settings.txt ;;"
        )
        result.settings_sources.append(
            f'        "|${{install_conf_host_by_service[{addon}]}}"'
        )
        for callback, target in callback_targets.items():
            target.extend(rendered_addon_callback(addon, callback, callback_values))

    return result


def smoke_test_template_values(
    services: dict[str, dict[str, str]],
) -> dict[str, str]:
    """Compile profile smoke checks independently from installer callbacks."""
    checks: list[str] = []
    for name, service in services.items():
        checks.extend(
            rendered_profile_callback(
                service["PROFILE"],
                "smoke-profile-checks",
                {
                    "SERVICE_NAME": name,
                    "SERVICE_NAME_SHELL": shlex.quote(name),
                },
            )
        )
    return {
        "SMOKE_SERVICES_LITERAL": bash_array(list(services)),
        "SMOKE_PROFILE_CHECKS": "\n".join(checks),
    }


def container_installer_template_values(config: dict[str, Any]) -> dict[str, str]:
    """Merge generic, profile, add-on, and smoke-test compiler results."""
    services = normalized_services(config)
    addons = normalized_addons(config)
    compilation = service_container_installer_compilation(services)
    compilation.extend(profile_container_installer_compilation(services))
    compilation.extend(addon_container_installer_compilation(config, addons))
    return {
        **compilation.template_values(),
        **smoke_test_template_values(services),
    }


def deployment_shape(config: dict[str, Any]) -> str:
    if owns_profile_artifacts(config):
        return f"profile:{selected_profile(config)}"
    return "multi-service"


def rendered_artifacts(config: dict[str, Any]) -> list[tuple[Path, bytes]]:
    """Render every application-owned artifact for a normalized config."""
    if "SERVICES" not in config:
        raise ValueError(
            "Projects must use the canonical SERVICES descriptor"
        )
    render_values = scalar_values(config)
    if owns_profile_artifacts(config):
        owned_name, _ = owned_profile_service(config) or ("", {})
        render_values.update(normalized_services(config)[owned_name])
        # Root profile artifacts are rendered separately from Compose service
        # fragments, so expose the owning SERVICES key to those templates too.
        render_values["SERVICE_NAME"] = owned_name
    render_values.update(container_installer_template_values(config))
    render_values.update(documentation_template_values(config))
    render_values.update(settings_template_values(config))

    artifacts: list[tuple[Path, bytes]] = []
    for template, relative in selected_templates(config):
        artifacts.append((relative, render(template, render_values)))
    artifacts.extend(orchestrator_artifacts(config))
    return artifacts


def validate_deployment_shape(state: dict, config: dict[str, Any]) -> None:
    """Reject synchronization or checking with an incompatible topology."""
    shape = deployment_shape(config)
    old_config = state.get("config", {})
    old_shape = deployment_shape(old_config) if old_config else shape
    if state.get("files") and old_shape != shape:
        raise ValueError(
            f"Cannot change initialized deployment shape from {old_shape!r} to "
            f"{shape!r}; initialize a new target to avoid mixing generated files"
        )


def classify_artifact(
    destination: Path, content: bytes, old_hash: str | None
) -> tuple[str, str | None, Path]:
    """Classify one artifact consistently for check and sync."""
    candidate = destination.with_name(destination.name + ".bu-isciii-update")
    expected_hash = digest(content)
    current_hash = digest(destination.read_bytes()) if destination.exists() else None
    candidate_hash = digest(candidate.read_bytes()) if candidate.exists() else None

    # A candidate is the durable marker for unresolved managed drift.
    if candidate_hash == expected_hash and current_hash != expected_hash:
        status = (
            "managed-drift-without-update"
            if old_hash == expected_hash
            else "managed-drift-with-update"
        )
        return status, current_hash, candidate
    if current_hash is None:
        return "missing", current_hash, candidate
    if current_hash == expected_hash:
        return "current", current_hash, candidate
    if old_hash is not None and current_hash == old_hash:
        return "update-available", current_hash, candidate
    if old_hash == expected_hash:
        return "managed-drift-without-update", current_hash, candidate
    return "managed-drift-with-update", current_hash, candidate


CONFIG_ASSIGNMENT_RE = re.compile(
    rb"^[ \t]*(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=",
    re.MULTILINE,
)


def schema_managed_settings(relative: Path) -> bool:
    """Return whether values are local but assignment names are standardized."""
    parts = relative.parts
    if len(parts) == 2 and parts[0] == "conf":
        return bool(re.fullmatch(r"docker_(?:production|test)_settings\.txt", parts[1]))
    if len(parts) == 3 and parts[0] == "conf":
        return bool(
            re.fullmatch(
                rf"{re.escape(parts[1])}_(?:production|test)_settings\.txt",
                parts[2],
            )
        )
    return False


def config_assignment_names(content: bytes) -> list[str]:
    """Extract shell assignment names without evaluating operator input."""
    return [match.decode("ascii") for match in CONFIG_ASSIGNMENT_RE.findall(content)]


def config_schema_differences(
    current: bytes, expected: bytes
) -> tuple[list[str], list[str]]:
    """Return missing standard names and duplicate local assignment names."""
    expected_names = set(config_assignment_names(expected))
    current_names = config_assignment_names(current)
    counts = {name: current_names.count(name) for name in set(current_names)}
    missing = sorted(expected_names - set(current_names))
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    return missing, duplicates


def merge_missing_config_assignments(current: bytes, expected: bytes) -> bytes:
    """Append only missing standard assignments, preserving every local value."""
    current_names = set(config_assignment_names(current))
    missing_lines: list[bytes] = []
    for line in expected.splitlines():
        match = CONFIG_ASSIGNMENT_RE.match(line)
        if not match:
            continue
        name = match.group(1).decode("ascii")
        if name not in current_names:
            missing_lines.append(line)
            current_names.add(name)
    if not missing_lines:
        return current
    merged = current.rstrip(b"\n")
    return (
        merged
        + b"\n\n# Added from the BU-ISCIII configuration schema; review local values.\n"
        + b"\n".join(missing_lines)
        + b"\n"
    )


def print_config_schema_details(missing: list[str], duplicates: list[str]) -> None:
    if missing:
        print(f"  missing variables: {', '.join(missing)}")
    if duplicates:
        print(f"  duplicate variables: {', '.join(duplicates)}")


def schema_managed_json(relative: Path) -> bool:
    """Return whether a JSON artifact has standard keys but local values."""
    return relative.as_posix() == "nextstrain/auspice-config.json"


def load_json_object(content: bytes) -> tuple[Any, list[str]]:
    """Parse JSON without silently accepting duplicate object keys."""
    duplicates: list[str] = []

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                duplicates.append(key)
            result[key] = value
        return result

    parsed = json.loads(content.decode("utf-8"), object_pairs_hook=object_pairs)
    return parsed, sorted(set(duplicates))


def json_schema_differences(
    current: Any, expected: Any, prefix: str = ""
) -> tuple[list[str], list[str]]:
    """Compare required object keys while treating scalar values as local."""
    if not isinstance(expected, dict):
        return [], []
    if not isinstance(current, dict):
        return [], [prefix or "<root>"]

    missing: list[str] = []
    object_conflicts: list[str] = []
    for key, expected_value in expected.items():
        path = f"{prefix}.{key}" if prefix else key
        if key not in current:
            missing.append(path)
            continue
        nested_missing, nested_conflicts = json_schema_differences(
            current[key], expected_value, path
        )
        missing.extend(nested_missing)
        object_conflicts.extend(nested_conflicts)
    return missing, object_conflicts


def merge_missing_json_properties(current: Any, expected: Any) -> Any:
    """Recursively add standard properties without replacing local values."""
    if not isinstance(expected, dict) or not isinstance(current, dict):
        return current
    for key, expected_value in expected.items():
        if key not in current:
            current[key] = expected_value
        else:
            merge_missing_json_properties(current[key], expected_value)
    return current


def print_json_schema_details(
    missing: list[str],
    duplicates: list[str],
    object_conflicts: list[str],
    error: str | None,
) -> None:
    if missing:
        print(f"  missing properties: {', '.join(missing)}")
    if duplicates:
        print(f"  duplicate properties: {', '.join(duplicates)}")
    if object_conflicts:
        print(f"  expected objects: {', '.join(object_conflicts)}")
    if error:
        print(f"  invalid JSON: {error}")


def classify_json_schema(
    current_content: bytes, expected_content: bytes
) -> tuple[str, list[str], list[str], list[str], str | None, Any, Any]:
    """Classify a JSON key schema while retaining parsed values for merging."""
    expected, expected_duplicates = load_json_object(expected_content)
    if expected_duplicates:
        raise ValueError(
            "Standard JSON contains duplicate properties: "
            + ", ".join(expected_duplicates)
        )
    try:
        current, duplicates = load_json_object(current_content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return "contract-drift", [], [], [], str(error), None, expected
    missing, object_conflicts = json_schema_differences(current, expected)
    status = (
        "contract-drift"
        if duplicates or object_conflicts
        else "update-available"
        if missing
        else "current"
    )
    return status, missing, duplicates, object_conflicts, None, current, expected


DJANGO_SETTINGS_PLACEHOLDERS = (
    "djangodebug",
    "djangoallowedhosts",
    "djangocsrftrustedorigins",
    "djangouser",
    "djangopass",
    "djangohost",
    "djangoport",
    "djangodbname",
    "dbconnmaxage",
    "emailhostserver",
    "emailport",
    "emailhostuser",
    "emailhostpassword",
    "emailhosttls",
)
DJANGO_SETTINGS_ASSIGNMENTS = (
    "SECRET_KEY",
    "DEBUG",
    "ALLOWED_HOSTS",
    "CSRF_TRUSTED_ORIGINS",
    "ROOT_URLCONF",
    "WSGI_APPLICATION",
    "DATABASES",
    "STATIC_ROOT",
    "MEDIA_ROOT",
)


def schema_managed_django_settings(relative: Path) -> bool:
    return relative.as_posix() == "conf/template_settings.py"


def top_level_python_assignments(tree: ast.AST) -> set[str]:
    assignments: set[str] = set()
    for node in getattr(tree, "body", []):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                assignments.add(target.id)
    return assignments


def django_settings_contract(
    target: Path, config: dict[str, Any], content: bytes
) -> tuple[list[str], list[str], list[str], str | None]:
    """Validate renderer placeholders without constraining application settings."""
    try:
        source = content.decode("utf-8")
        tree = ast.parse(source, filename="conf/template_settings.py")
    except (UnicodeDecodeError, SyntaxError) as error:
        return [], [], [], str(error)

    placeholder_counts = {token: 0 for token in DJANGO_SETTINGS_PLACEHOLDERS}
    application_tokens: set[str] = set()
    for node in ast.walk(tree):
        value: str | None = None
        if isinstance(node, ast.Name):
            value = node.id
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
        if value in placeholder_counts:
            placeholder_counts[value] += 1
        if isinstance(node, ast.Name) and re.fullmatch(
            r"settingsconf_[A-Z][A-Z0-9_]*", node.id
        ):
            application_tokens.add(node.id.removeprefix("settingsconf_"))
    missing_placeholders = sorted(
        token for token, count in placeholder_counts.items() if count == 0
    )
    duplicate_placeholders = sorted(
        token for token, count in placeholder_counts.items() if count > 1
    )
    assignments = top_level_python_assignments(tree)
    missing_assignments = sorted(set(DJANGO_SETTINGS_ASSIGNMENTS) - assignments)

    owned = owned_profile_service(config)
    if owned:
        _, service = owned
        for setting_path in (service["INSTALL_CONF"], service["TEST_INSTALL_CONF"]):
            path = target / setting_path
            available = (
                set(config_assignment_names(path.read_bytes())) if path.is_file() else set()
            )
            missing_assignments.extend(
                f"{token} in {setting_path}"
                for token in sorted(application_tokens)
                if token not in available
            )
    return (
        sorted(missing_placeholders),
        sorted(duplicate_placeholders),
        sorted(set(missing_assignments)),
        None,
    )


def print_django_settings_details(
    missing_placeholders: list[str],
    duplicate_placeholders: list[str],
    missing_assignments: list[str],
    error: str | None,
) -> None:
    if missing_placeholders:
        print(f"  missing placeholders: {', '.join(missing_placeholders)}")
    if duplicate_placeholders:
        print(f"  duplicate placeholders: {', '.join(duplicate_placeholders)}")
    if missing_assignments:
        print(f"  missing assignments: {', '.join(missing_assignments)}")
    if error:
        print(f"  invalid Python: {error}")


def check_baseline(target: Path, config: dict[str, Any]) -> int:
    """Report generated-file drift without modifying the target repository."""
    state = load_state(target)
    validate_deployment_shape(state, config)
    old_hashes = state.get("files", {})
    expected_paths: set[str] = set()
    drift = 0

    for relative, content in rendered_artifacts(config):
        relative_name = relative.as_posix()
        expected_paths.add(relative_name)
        destination = target / relative
        current_content = destination.read_bytes() if destination.exists() else None
        content = preserve_application_blocks(content, current_content)
        old_hash = old_hashes.get(relative_name)
        missing: list[str] = []
        duplicates: list[str] = []
        json_missing: list[str] = []
        json_duplicates: list[str] = []
        json_object_conflicts: list[str] = []
        json_error: str | None = None
        settings_missing_placeholders: list[str] = []
        settings_duplicate_placeholders: list[str] = []
        settings_missing_assignments: list[str] = []
        settings_error: str | None = None
        if schema_managed_settings(relative) and current_content is not None:
            missing, duplicates = config_schema_differences(current_content, content)
            if duplicates:
                status = "contract-drift"
            elif missing:
                status = "update-available"
            else:
                status = "current"
        elif schema_managed_json(relative) and current_content is not None:
            (
                status,
                json_missing,
                json_duplicates,
                json_object_conflicts,
                json_error,
                _,
                _,
            ) = classify_json_schema(current_content, content)
        elif schema_managed_django_settings(relative) and current_content is not None:
            (
                settings_missing_placeholders,
                settings_duplicate_placeholders,
                settings_missing_assignments,
                settings_error,
            ) = django_settings_contract(target, config, current_content)
            status = (
                "contract-drift"
                if settings_missing_placeholders
                or settings_duplicate_placeholders
                or settings_missing_assignments
                or settings_error
                else "current"
            )
        else:
            status, _, _ = classify_artifact(destination, content, old_hash)

        print(f"{status:16} {relative}")
        print_config_schema_details(missing, duplicates)
        print_json_schema_details(
            json_missing, json_duplicates, json_object_conflicts, json_error
        )
        print_django_settings_details(
            settings_missing_placeholders,
            settings_duplicate_placeholders,
            settings_missing_assignments,
            settings_error,
        )
        if status != "current":
            drift += 1

    for relative_name in sorted(set(old_hashes) - expected_paths):
        print(f"obsolete         {relative_name}")
        drift += 1

    shared_drift = check_shared(target)
    drift += shared_drift
    print(f"Deployment baseline check found {drift} synchronization issue(s).")
    return 1 if drift else 0


def synchronize(target: Path, config: dict[str, Any], initial: bool) -> int:
    state = load_state(target)
    if not initial:
        validate_deployment_shape(state, config)
    old_hashes = state.get("files", {})
    new_hashes: dict[str, str] = {}
    issues = 0

    for relative, content in rendered_artifacts(config):
        destination = target / relative
        current_content = destination.read_bytes() if destination.exists() else None
        content = preserve_application_blocks(content, current_content)
        new_hash = digest(content)
        old_hash = old_hashes.get(relative.as_posix())
        missing: list[str] = []
        duplicates: list[str] = []
        json_missing: list[str] = []
        json_duplicates: list[str] = []
        json_object_conflicts: list[str] = []
        json_error: str | None = None
        current_json: Any = None
        expected_json: Any = None
        settings_missing_placeholders: list[str] = []
        settings_duplicate_placeholders: list[str] = []
        settings_missing_assignments: list[str] = []
        settings_error: str | None = None
        update_kind: str | None = None
        if schema_managed_settings(relative) and current_content is not None:
            missing, duplicates = config_schema_differences(current_content, content)
            if duplicates:
                status = "contract-drift"
            elif missing:
                status = "update-available"
                update_kind = "config-schema"
            else:
                status = "current"
            candidate = destination.with_name(destination.name + ".bu-isciii-update")
        elif schema_managed_json(relative) and current_content is not None:
            (
                status,
                json_missing,
                json_duplicates,
                json_object_conflicts,
                json_error,
                current_json,
                expected_json,
            ) = classify_json_schema(current_content, content)
            if status == "update-available":
                update_kind = "json-schema"
            candidate = destination.with_name(destination.name + ".bu-isciii-update")
        elif schema_managed_django_settings(relative) and current_content is not None:
            (
                settings_missing_placeholders,
                settings_duplicate_placeholders,
                settings_missing_assignments,
                settings_error,
            ) = django_settings_contract(target, config, current_content)
            status = (
                "contract-drift"
                if settings_missing_placeholders
                or settings_duplicate_placeholders
                or settings_missing_assignments
                or settings_error
                else "current"
            )
            candidate = destination.with_name(destination.name + ".bu-isciii-update")
        else:
            status, _, candidate = classify_artifact(destination, content, old_hash)

        destination.parent.mkdir(parents=True, exist_ok=True)
        if status == "current":
            print(f"current  {relative}")
        elif status == "update-available" and update_kind == "config-schema":
            destination.write_bytes(merge_missing_config_assignments(current_content, content))
            print(f"updated  {relative}")
            if missing:
                print(f"  added variables: {', '.join(missing)}")
        elif status == "update-available" and update_kind == "json-schema":
            merged_json = merge_missing_json_properties(current_json, expected_json)
            destination.write_text(
                json.dumps(merged_json, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"updated  {relative}")
            if json_missing:
                print(f"  added properties: {', '.join(json_missing)}")
        elif status == "contract-drift":
            print(f"contract-drift {relative}")
            print_config_schema_details(missing, duplicates)
            print_json_schema_details(
                json_missing, json_duplicates, json_object_conflicts, json_error
            )
            print_django_settings_details(
                settings_missing_placeholders,
                settings_duplicate_placeholders,
                settings_missing_assignments,
                settings_error,
            )
            issues += 1
        elif status in {"missing", "update-available"}:
            destination.write_bytes(content)
            if executable(relative):
                destination.chmod(destination.stat().st_mode | 0o111)
            print(f"updated  {relative}")
        elif status in {
            "managed-drift-without-update",
            "managed-drift-with-update",
        }:
            if not candidate.exists() or digest(candidate.read_bytes()) != new_hash:
                candidate.write_bytes(content)
            print(f"{status} {relative} -> {candidate.name}")
            issues += 1
        else:
            raise ValueError(f"Unsupported synchronization status: {status}")

        if status == "managed-drift-with-update" and old_hash is not None:
            new_hashes[relative.as_posix()] = old_hash
        else:
            new_hashes[relative.as_posix()] = new_hash

    # Keep the previous central baseline while a central update and local managed
    # drift remain unresolved; otherwise record the latest rendered standard.
    write_state(target, config, new_hashes)
    # Shared libraries are centrally owned exact copies, so a generated
    # installer must never be left pointing at missing or stale helpers.
    synchronize_shared(target, check_only=False)
    verb = "Initialized" if initial else "Synchronized"
    print(f"{verb} {target} with {issues} unresolved issue(s).")
    return 2 if issues else 0


def shared_destination(source: Path) -> Path:
    return Path("deployment/lib") / source.relative_to(SHARED_LIB)


def check_shared(target: Path) -> int:
    """Report shared-library drift without writing to the target."""
    drift = 0
    for source in sorted(SHARED_LIB.rglob("*.sh")):
        relative = shared_destination(source)
        destination = target / relative
        if (
            destination.exists()
            and digest(destination.read_bytes()) == digest(source.read_bytes())
        ):
            print(f"{'current':16} {relative}")
            continue
        status = "missing" if not destination.exists() else "modified"
        print(f"{status:16} {relative}")
        drift += 1
    return drift


def synchronize_shared(target: Path, check_only: bool) -> int:
    if check_only:
        drift = check_shared(target)
        print(f"Shared library check found {drift} drifted file(s).")
        return 1 if drift else 0

    drift = 0
    for source in sorted(SHARED_LIB.rglob("*.sh")):
        relative = shared_destination(source)
        destination = target / relative
        content = source.read_bytes()
        if destination.exists() and digest(destination.read_bytes()) == digest(content):
            print(f"current  {relative}")
            continue
        drift += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        print(f"updated  {relative}")

    print(f"Shared libraries synchronized with {drift} update(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "sync"):
        sub = subparsers.add_parser(command)
        sub.add_argument("target", type=Path)
        sub.add_argument("--config", type=Path)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("target", type=Path)
    for command in ("check-lib", "sync-lib"):
        sub = subparsers.add_parser(command)
        sub.add_argument("target", type=Path)
    args = parser.parse_args()

    target = args.target.resolve()
    if args.command in {"check-lib", "sync-lib"}:
        return synchronize_shared(target, args.command == "check-lib")

    state = load_state(target)
    if getattr(args, "config", None):
        config = load_json(args.config.resolve())
    elif args.command in {"sync", "check"} and state.get("config"):
        config = state["config"]
    else:
        parser.error(
            "--config is required for init and for sync/check without saved state"
        )

    if args.command == "init" and (target / STATE_DIR / STATE_FILE).exists():
        parser.error(f"{target} is already initialized; use sync")
    if args.command == "check":
        return check_baseline(target, config)
    target.mkdir(parents=True, exist_ok=True)
    return synchronize(target, config, args.command == "init")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
