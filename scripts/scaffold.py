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

    def extend(self, other: ContainerInstallerCompilation) -> None:
        """Append another compiler result while preserving declaration order."""
        for field_name in vars(self):
            getattr(self, field_name).extend(getattr(other, field_name))

    def template_values(self) -> dict[str, str]:
        """Convert collected fragments into tokens used by common templates."""
        return {
            "INSTALL_SERVICES_LITERAL": bash_array(self.install_services),
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
    # into deployment/<addon>/ immediately before Compose validation.
    for addon in normalized_addons(config):
        source_root = ADDON_TEMPLATES / addon / "conf"
        for template in sorted(source_root.glob("*.conf.tmpl")):
            relative = Path("conf") / addon / template.name.removesuffix(".tmpl")
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
    }
    services: dict[str, dict[str, str]] = {}
    for raw_name, raw_service in raw.items():
        name = str(raw_name)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise ValueError(f"Invalid service name: {name!r}")
        if not isinstance(raw_service, dict):
            raise ValueError(f"SERVICES.{name} must be a JSON object")
        service = {str(key): str(value) for key, value in raw_service.items()}
        unknown_keys = sorted(service.keys() - allowed_keys)
        if unknown_keys:
            raise ValueError(
                f"SERVICES.{name} contains unsupported keys: "
                + ", ".join(unknown_keys)
            )
        profile = service.get("PROFILE", "").lower()
        if profile not in {"django", "react-vite"}:
            raise ValueError(
                f"SERVICES.{name}.PROFILE must be django or react-vite"
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
        unknown_options = sorted(
            set(normalized_options) - {"CONFIG_SERVICE", "MOUNTS"}
        )
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
        # Every add-on consumes its section from one application settings file;
        # add-ons never introduce another settings source of their own.
        normalized_options["CONFIG_SERVICE"] = config_service
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
    """Append rendered add-on fragments to their owning application settings."""
    sections = [
        rendered_addon_settings(config, addon, mode)
        for addon, options in normalized_addons(config).items()
        if options["CONFIG_SERVICE"] == service_name
    ]
    return "\n\n".join(sections) or "# No infrastructure add-on settings are owned by this service."


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


def compose_service_block(
    name: str, service: dict[str, str], mode: str
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


def addon_dependency_services(addon: str) -> list[str]:
    """Read healthy service names another add-on may depend upon."""
    path = ADDON_TEMPLATES / addon / "compose" / "dependency-services.txt.tmpl"
    if not path.is_file():
        return []
    names = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
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
    dependency_names = list(services)
    for selected_addon in addons:
        if selected_addon != addon:
            dependency_names.extend(addon_dependency_services(selected_addon))
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
    compilations = [
        compose_service_block(name, service, mode)
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
    selected_profiles = list(
        dict.fromkeys(service["PROFILE"] for service in services.values())
    )

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
        persistence_rows.append(
            rendered_documentation_fragment(
                "profile",
                service["PROFILE"],
                "persistence-rows.md",
                {"SERVICE_NAME": name},
            )
        )

    profile_notes = [
        rendered_documentation_fragment("profile", profile, "profile.md", {})
        for profile in selected_profiles
    ]
    addon_notes = [
        rendered_documentation_fragment("addon", addon, "addon.md", {})
        for addon in addons
    ]
    for addon in addons:
        persistence = ADDON_TEMPLATES / addon / "documentation" / "persistence-rows.md.tmpl"
        if persistence.is_file():
            persistence_rows.append(
                rendered_documentation_fragment(
                    "addon", addon, "persistence-rows.md", {}
                )
            )
    if not addon_notes:
        addon_notes.append(
            rendered_documentation_fragment("common", "", "no-addons.md", {})
        )

    return {
        "SERVICE_INVENTORY_ROWS": "\n".join(service_rows),
        "PROFILE_DOCUMENTATION": "\n".join(profile_notes),
        "ADDON_DOCUMENTATION": "\n".join(addon_notes),
        "PERSISTENCE_ROWS": "\n".join(persistence_rows),
        "CONFIG_MAP_EXAMPLES": " ".join(config_map_examples),
    }


def settings_template_values(config: dict[str, Any]) -> dict[str, str]:
    """Build only profile-settings sections and their add-on documentation."""
    services = normalized_services(config)
    owned = owned_profile_service(config)
    settings_owner = owned[0] if owned else next(iter(services))
    return {
        "PRODUCTION_ADDON_SETTINGS": addon_settings_section(
            config, settings_owner, "production"
        ),
        "TEST_ADDON_SETTINGS": addon_settings_section(config, settings_owner, "test"),
        "ADDON_SETTINGS_DOCUMENTATION": addon_settings_documentation(
            config, settings_owner
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


def addon_permission_services(addon: str) -> list[str]:
    """Read permission-repair service names declared by an add-on."""
    template = (
        ADDON_TEMPLATES
        / addon
        / "container_install"
        / "permission-services.txt.tmpl"
    )
    if not template.is_file():
        return []
    names = [line.strip() for line in template.read_text(encoding="utf-8").splitlines()]
    names = [name for name in names if name and not name.startswith("#")]
    for name in names:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", name):
            raise ValueError(f"Invalid permission service {name!r} in {template}")
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
            "CONFIG_SERVICE": config_service,
            "CONFIG_SERVICE_SHELL": shlex.quote(config_service),
        }
        result.permission_services.extend(addon_permission_services(addon))
        for callback, target in callback_targets.items():
            target.extend(rendered_addon_callback(addon, callback, callback_values))

        config_reference = f'"${{install_conf_host_by_service[{config_service}]}}"'
        for key in addon_setting_keys(config, addon):
            result.deployment_values.append(
                f'        "{key}|$(config_value_or_default {key} '
                f"{config_reference} '')\""
            )
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
