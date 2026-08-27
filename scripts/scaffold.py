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
            if key != "API"
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
        service["API"] = "true" if raw_api else "false"
        service["PROFILE"] = profile
        service.setdefault("IMAGE", f"{name.replace('_', '-')}:local")
        service.setdefault("DOCKERFILE", "Dockerfile")
        services[name] = service
    return services


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
            supported_options.add("ADMIN_ACCESS")
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


def addon_settings_documentation(config: dict[str, Any], service_name: str) -> str:
    sections = [
        rendered_addon_settings_documentation(config, addon)
        for addon, options in normalized_addons(config).items()
        if options["CONFIG_SERVICE"] == service_name
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
    oidc_service: str | None,
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
        "OPTIONAL_SERVICE_ENVIRONMENT": optional_django_compose_environment(
            service,
            mode,
            name == oidc_service,
            name == oidc_service and keycloak_admin_access,
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
        support_lines=optional_fragment("support-services"),
        volume_lines=optional_fragment("volumes"),
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
    oidc_service = (
        str(addons["keycloak"]["CONFIG_SERVICE"])
        if "keycloak" in addons
        else None
    )
    keycloak_admin_access = bool(
        "keycloak" in addons and addons["keycloak"].get("ADMIN_ACCESS", False)
    )
    compilations = [
        compose_service_block(
            name,
            service,
            mode,
            oidc_service,
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
    primary_service = next(iter(services))

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
                "persistence-rows.md",
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
    has_oidc = (
        "keycloak" in addons
        and addons["keycloak"]["CONFIG_SERVICE"] == settings_owner
    )
    has_keycloak_admin = bool(
        has_oidc and addons["keycloak"].get("ADMIN_ACCESS", False)
    )
    return {
        "PRODUCTION_ADDON_SETTINGS": addon_settings_section(
            config, settings_owner, "production"
        ),
        "TEST_ADDON_SETTINGS": addon_settings_section(config, settings_owner, "test"),
        "ADDON_SETTINGS_DOCUMENTATION": addon_settings_documentation(
            config, settings_owner
        ),
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


def synchronize(target: Path, config: dict[str, Any], initial: bool) -> int:
    state = load_state(target)
    if "SERVICES" not in config:
        raise ValueError(
            "Projects must use the canonical SERVICES descriptor"
        )
    shape = deployment_shape(config)
    old_config = state.get("config", {})
    old_shape = deployment_shape(old_config) if old_config else shape
    if not initial and state.get("files") and old_shape != shape:
        raise ValueError(
            f"Cannot change initialized deployment shape from {old_shape!r} to "
            f"{shape!r}; initialize a new target to avoid mixing generated files"
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
    old_hashes = state.get("files", {})
    new_hashes: dict[str, str] = {}
    conflicts = 0

    artifacts: list[tuple[Path, bytes]] = []
    for template, relative in selected_templates(config):
        artifacts.append((relative, render(template, render_values)))
    artifacts.extend(orchestrator_artifacts(config))

    for relative, content in artifacts:
        destination = target / relative
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
    # Shared libraries are centrally owned exact copies, so a generated
    # installer must never be left pointing at missing or stale helpers.
    synchronize_shared(target, check_only=False)
    verb = "Initialized" if initial else "Synchronized"
    print(f"{verb} {target} with {conflicts} conflict(s).")
    return 2 if conflicts else 0


def shared_destination(source: Path) -> Path:
    return Path("deployment/lib") / source.relative_to(SHARED_LIB)


def synchronize_shared(target: Path, check_only: bool) -> int:
    drift = 0
    for source in sorted(SHARED_LIB.rglob("*.sh")):
        relative = shared_destination(source)
        destination = target / relative
        content = source.read_bytes()
        if destination.exists() and digest(destination.read_bytes()) == digest(content):
            print(f"current  {relative}")
            continue
        drift += 1
        if check_only:
            status = "missing" if not destination.exists() else "modified"
            print(f"{status:8} {relative}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        print(f"updated  {relative}")

    if check_only:
        print(f"Shared library check found {drift} drifted file(s).")
        return 1 if drift else 0
    print(f"Shared libraries synchronized with {drift} update(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "sync"):
        sub = subparsers.add_parser(command)
        sub.add_argument("target", type=Path)
        sub.add_argument("--config", type=Path)
    for command in ("check-lib", "sync-lib"):
        sub = subparsers.add_parser(command)
        sub.add_argument("target", type=Path)
    args = parser.parse_args()

    target = args.target.resolve()
    if args.command in {"check-lib", "sync-lib"}:
        return synchronize_shared(target, args.command == "check-lib")

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
