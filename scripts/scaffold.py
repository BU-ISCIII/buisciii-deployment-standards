#!/usr/bin/env python3
"""Create or safely synchronize a BU-ISCIII deployment baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "scaffold" / "templates"
COMMON_TEMPLATES = TEMPLATES / "common"
COMMON_COMPOSE_TEMPLATE = COMMON_TEMPLATES / "docker-compose.yml.tmpl"
PROFILE_TEMPLATES = TEMPLATES / "profiles"
SHARED_LIB = ROOT / "lib"
STATE_DIR = ".bu-isciii-deployment"
STATE_FILE = "state.json"
TOKEN = re.compile(r"{{([A-Z0-9_]+)}}")


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
    if "PROFILE" in config:
        profile = str(config["PROFILE"]).strip().lower()
    else:
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


def uses_service_descriptor(config: dict[str, Any]) -> bool:
    return "SERVICES" in config


def owned_profile_service(
    config: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    """Return the one service whose framework artifacts live in this repo."""
    if not uses_service_descriptor(config):
        return None
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
    return not uses_service_descriptor(config) or owned_profile_service(config) is not None


def selected_templates(config: dict[str, Any]) -> list[tuple[Path, Path]]:
    """Return common templates plus standalone framework-owned artifacts."""
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
            relative = destination_for(template, source_root)
            if relative in destinations:
                raise ValueError(
                    f"Template destination {relative} is defined by common and profile files"
                )
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
    if raw is None:
        profile = selected_profile(config)
        slug = str(config.get("APP_SLUG", "app"))
        raw_service: dict[str, Any] = {
            "PROFILE": profile,
            "BUILD_CONTEXT": ".",
            "DOCKERFILE": "Dockerfile",
            "INSTALL_CONF": "conf/docker_production_settings.txt",
            "TEST_INSTALL_CONF": "conf/docker_test_settings.txt",
            "TEST_BUILD_INSTALL_CONF": "conf/docker_test_settings.txt",
            "APP_PORT": config.get("APP_PORT", "8000"),
            "APP_UID": config.get("APP_UID", "1212"),
            "APP_GID": config.get("APP_GID", "1212"),
            "IMAGE": f"{slug}:local",
            "REPO_PATH": f"/srv/{slug}",
        }
        if profile == "django":
            raw_service.update(
                {
                    "PROJECT_MODULE": config.get("PROJECT_MODULE", "app"),
                    "INSTALL_PATH": config.get("INSTALL_PATH", f"/opt/{slug}"),
                    "CONTAINER_INSTALL_CONF": "conf/runtime_install_settings.txt",
                }
            )
        raw = {"app": raw_service}
    if not isinstance(raw, dict) or not raw:
        raise ValueError("SERVICES must be a non-empty JSON object")
    services: dict[str, dict[str, str]] = {}
    for raw_name, raw_service in raw.items():
        name = str(raw_name)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise ValueError(f"Invalid service name: {name!r}")
        if not isinstance(raw_service, dict):
            raise ValueError(f"SERVICES.{name} must be a JSON object")
        service = {str(key): str(value) for key, value in raw_service.items()}
        profile = service.get("PROFILE", "").lower()
        if profile not in {"django", "react-vite"}:
            raise ValueError(
                f"SERVICES.{name}.PROFILE must be django or react-vite"
            )
        for required in ("BUILD_CONTEXT", "INSTALL_CONF", "APP_PORT", "APP_UID", "APP_GID"):
            if not service.get(required):
                raise ValueError(f"SERVICES.{name}.{required} is required")
        if profile == "django":
            for required in ("PROJECT_MODULE", "INSTALL_PATH", "INSTALL_CONF"):
                if not service.get(required):
                    raise ValueError(f"SERVICES.{name}.{required} is required")
        service["PROFILE"] = profile
        service.setdefault("IMAGE", f"{name.replace('_', '-')}:local")
        service.setdefault("DOCKERFILE", "Dockerfile")
        service.setdefault("TEST_INSTALL_CONF", service["INSTALL_CONF"])
        service.setdefault("TEST_BUILD_INSTALL_CONF", "conf/docker_test_settings.txt")
        service.setdefault("CONTAINER_INSTALL_CONF", "conf/runtime_install_settings.txt")
        services[name] = service
    return services


def normalized_addons(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = config.get("ADDONS", {})
    if isinstance(raw, str):
        raw = {name.strip(): {} for name in raw.split(",") if name.strip()}
    elif isinstance(raw, list):
        raw = {str(name): {} for name in raw}
    if not isinstance(raw, dict):
        raise ValueError("ADDONS must be an object, list, or comma-separated string")
    addons: dict[str, dict[str, Any]] = {}
    for raw_name, options in raw.items():
        name = str(raw_name).lower()
        if name not in {"apache", "keycloak"}:
            raise ValueError(f"Unsupported add-on: {name}")
        if options is None:
            options = {}
        if not isinstance(options, dict):
            raise ValueError(f"ADDONS.{name} must be a JSON object")
        if name in {"apache", "keycloak"} and not options.get("INSTALL_CONF"):
            raise ValueError(f"ADDONS.{name}.INSTALL_CONF is required")
        addons[name] = options
    return addons


def env_prefix(service_name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", service_name.upper())


def compose_variable(prefix: str, key: str, default: str | None = None) -> str:
    name = f"{prefix}_{key}"
    if default is None:
        return f"${{{name}:?{name} is required}}"
    return f"${{{name}:-{default}}}"


def compose_service_block(
    name: str, service: dict[str, str], mode: str
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return service lines plus extra services, volumes, and secrets."""
    prefix = env_prefix(name)
    profile = service["PROFILE"]
    port = service["APP_PORT"]
    image = service["IMAGE"]
    context = service["BUILD_CONTEXT"]
    dockerfile = service["DOCKERFILE"]
    lines = [f"  # BEGIN BU-ISCIII SERVICE: {name} ({profile})", f"  {name}:"]
    lines += [f"    image: {compose_variable(prefix, 'IMAGE', image)}", "    build:", f"      context: {json.dumps(context)}", f"      dockerfile: {json.dumps(dockerfile)}", "      args:", "        GIT_REVISION: ${GIT_REVISION:-current}"]
    extras: list[str] = []
    volumes: list[str] = []
    secrets: list[str] = []

    if profile == "django":
        install_path = service["INSTALL_PATH"]
        module = service["PROJECT_MODULE"]
        conf = service["CONTAINER_INSTALL_CONF"] if mode == "prod" else service["TEST_BUILD_INSTALL_CONF"]
        lines += [
            f"        INSTALL_CONF: {json.dumps(conf)}",
            f"        USE_INSTALL_CONF_SECRET: {json.dumps('true' if mode == 'prod' else 'false')}",
            f"        RENDER_DJANGO_SETTINGS: {json.dumps('false' if mode == 'prod' else 'true')}",
            f"        APP_UID: {compose_variable(prefix, 'APP_UID', service['APP_UID'])}",
            f"        APP_GID: {compose_variable(prefix, 'APP_GID', service['APP_GID'])}",
            f"        APP_INSTALL_PATH: {json.dumps(install_path)}",
        ]
        lines += [
            "    restart: unless-stopped",
            f"    user: {json.dumps(compose_variable(prefix, 'APP_UID', service['APP_UID']) + ':' + compose_variable(prefix, 'APP_GID', service['APP_GID']))}",
            "    environment:",
            f"      APP_MODE: {'prod' if mode == 'prod' else 'dev'}",
            f"      INSTALL_PATH: {json.dumps(install_path)}",
            f"      APP_INSTALL_PATH: {json.dumps(install_path)}",
            f"      APP_PORT: {compose_variable(prefix, 'APP_PORT', port)}",
            f"      PROJECT_MODULE: {json.dumps(module)}",
        ]
        db_host = compose_variable(prefix, "DB_HOST") if mode == "prod" else f"{name}_db"
        lines += [
            f"      DB_HOST: {db_host}",
            f"      DB_PORT: {compose_variable(prefix, 'DB_PORT', '3306')}",
            f"      DB_NAME: {compose_variable(prefix, 'DB_NAME', module if mode == 'test' else None)}",
            f"      DB_USER: {compose_variable(prefix, 'DB_USER', 'django' if mode == 'test' else None)}",
            f"      DB_PASSWORD: {compose_variable(prefix, 'DB_PASSWORD', 'djangopass' if mode == 'test' else None)}",
            f"      DJANGO_SECRET_KEY: {compose_variable(prefix, 'DJANGO_SECRET_KEY', 'test-only-change-me' if mode == 'test' else None)}",
            f"      DJANGO_ALLOWED_HOSTS: {compose_variable(prefix, 'DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0' if mode == 'test' else None)}",
        ]
        if mode == "test":
            lines += ["    depends_on:", f"      {name}_db:", "        condition: service_healthy"]
        lines += ["    volumes:"]
        if mode == "prod":
            host_data = compose_variable(prefix, "HOST_DATA_PATH")
            host_log = compose_variable(prefix, "HOST_LOG_PATH")
            settings_path = compose_variable(prefix, "DJANGO_SETTINGS_PATH")
            lines += [
                f"      - {host_data}/documents:{install_path}/documents:Z",
                f"      - {host_log}:{install_path}/logs:Z",
                f"      - {settings_path}:{install_path}/{module}/settings.py:Z",
                f"      - {name}_static:{install_path}/static:z",
            ]
            volumes.append(f"  {name}_static:")
        else:
            lines += [
                f"      - {name}_test_documents:{install_path}/documents:z",
                f"      - {name}_test_static:{install_path}/static:z",
            ]
            volumes += [f"  {name}_test_db:", f"  {name}_test_documents:", f"  {name}_test_static:"]
            extras += [
                f"  {name}_db:",
                "    image: docker.io/library/mysql:8.0",
                "    environment:",
                f"      MYSQL_DATABASE: {compose_variable(prefix, 'DB_NAME', module)}",
                f"      MYSQL_USER: {compose_variable(prefix, 'DB_USER', 'django')}",
                f"      MYSQL_PASSWORD: {compose_variable(prefix, 'DB_PASSWORD', 'djangopass')}",
                f"      MYSQL_ROOT_PASSWORD: {compose_variable(prefix, 'DB_ROOT_PASSWORD', 'root')}",
                "    healthcheck:",
                '      test: ["CMD-SHELL", "mysqladmin ping -h 127.0.0.1 -uroot -p$$MYSQL_ROOT_PASSWORD --silent"]',
                "      interval: 5s",
                "      timeout: 5s",
                "      retries: 20",
                f"    volumes: [{name}_test_db:/var/lib/mysql]",
                "    networks: [deployment_net]",
            ]
        lines += [
            "    healthcheck:",
            f"      test: [\"CMD\", \"python\", \"-c\", \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:{port}/health/', timeout=3)\"]",
            "      interval: 10s",
            "      timeout: 5s",
            "      retries: 12",
        ]
    else:
        vite_api_default = (
            service.get("TEST_VITE_API_BASE_URL", "http://127.0.0.1:8000")
            if mode == "test"
            else None
        )
        lines += [
            f"        VITE_API_BASE_URL: {compose_variable(prefix, 'VITE_API_BASE_URL', vite_api_default)}",
            "    restart: unless-stopped",
            f"    user: {json.dumps(compose_variable(prefix, 'APP_UID', service['APP_UID']) + ':' + compose_variable(prefix, 'APP_GID', service['APP_GID']))}",
            "    read_only: true",
            "    tmpfs:",
            "      - /tmp:size=16m,mode=1777",
            f"      - /var/cache/nginx:size=32m,uid={compose_variable(prefix, 'APP_UID', service['APP_UID'])},gid={compose_variable(prefix, 'APP_GID', service['APP_GID'])},mode=0750",
            f"      - /var/run:size=4m,uid={compose_variable(prefix, 'APP_UID', service['APP_UID'])},gid={compose_variable(prefix, 'APP_GID', service['APP_GID'])},mode=0750",
            "    healthcheck:",
            f"      test: [\"CMD\", \"wget\", \"-q\", \"-O\", \"/dev/null\", \"http://127.0.0.1:{port}/health/\"]",
            "      interval: 10s",
            "      timeout: 5s",
            "      retries: 12",
        ]
    lines += [
        "    ports:",
        f"      - {json.dumps('127.0.0.1:' + compose_variable(prefix, 'APP_PORT', port) + ':' + port)}",
        "    networks: [deployment_net]",
        f"  # END BU-ISCIII SERVICE: {name}",
    ]
    return lines, extras, volumes, secrets


def apache_proxy_configuration(services: dict[str, dict[str, str]], options: dict[str, Any]) -> bytes:
    routes = options.get("ROUTES")
    virtual_hosts = options.get("VIRTUAL_HOSTS")
    if routes is not None and virtual_hosts is not None:
        raise ValueError("ADDONS.apache must use either ROUTES or VIRTUAL_HOSTS, not both")

    def target_port(target_name: str) -> str:
        if target_name not in services and target_name != "keycloak":
            raise ValueError(f"Apache proxy targets unknown service {target_name!r}")
        return services[target_name]["APP_PORT"] if target_name in services else "8080"

    def django_mount_aliases(target_name: str, url_prefix: str, indent: str = "") -> list[str]:
        if target_name not in services or services[target_name]["PROFILE"] != "django":
            return []
        prefix = url_prefix.rstrip("/")
        static_url = f"{prefix}/static/"
        documents_url = f"{prefix}/documents/"
        return [
            f"{indent}ProxyPass {static_url} !",
            f"{indent}Alias {static_url} /var/www/{target_name}/static/",
            f'{indent}<Directory "/var/www/{target_name}/static">',
            f"{indent}    Require all granted",
            f"{indent}</Directory>",
            f"{indent}ProxyPass {documents_url} !",
            f"{indent}Alias {documents_url} /var/www/{target_name}/documents/",
            f'{indent}<Directory "/var/www/{target_name}/documents">',
            f"{indent}    Require all granted",
            f"{indent}</Directory>",
        ]

    header = [
        "# Generated reverse-proxy contract. Edit ADDONS.apache in project.json,",
        "# not this synchronized output.",
    ]
    if virtual_hosts is not None:
        if not isinstance(virtual_hosts, dict) or not virtual_hosts:
            raise ValueError("ADDONS.apache.VIRTUAL_HOSTS must map DNS names to service names")
        lines = header + [
            "# Separate virtual hosts are recommended for multi-app deployments and",
            "# identity providers because each service keeps its native root URL.",
        ]
        for hostname, target in virtual_hosts.items():
            server_name = str(hostname)
            if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", server_name):
                raise ValueError(f"Invalid Apache virtual-host ServerName: {server_name!r}")
            target_name = str(target)
            port = target_port(target_name)
            log_stem = re.sub(r"[^A-Za-z0-9_.-]", "_", server_name)
            lines += [
                "",
                "<VirtualHost *:8080>",
                f"    ServerName {server_name}",
                "    ProxyRequests Off",
                "    ProxyPreserveHost On",
                "    AllowEncodedSlashes NoDecode",
                '    RequestHeader set X-Forwarded-Proto "${APACHE_FORWARDED_PROTO}"',
                '    RequestHeader set X-Forwarded-Port "${APACHE_FORWARDED_PORT}"',
                f'    RequestHeader set X-Forwarded-Host "{server_name}"',
                "    LimitRequestBody ${APACHE_LIMIT_REQUEST_BODY}",
            ]
            lines += django_mount_aliases(target_name, "", "    ")
            lines += [
                f"    ProxyPass / http://{target_name}:{port}/",
                f"    ProxyPassReverse / http://{target_name}:{port}/",
                "    ProxyTimeout 120",
                "    TimeOut 120",
                f'    ErrorLog "logs/{log_stem}.error.log"',
                f'    CustomLog "logs/{log_stem}.access.log" combined',
                "</VirtualHost>",
            ]
        return ("\n".join(lines) + "\n").encode()

    if routes is None:
        react_services = [name for name, item in services.items() if item["PROFILE"] == "react-vite"]
        django_services = [name for name, item in services.items() if item["PROFILE"] == "django"]
        routes = {}
        if react_services:
            routes["/"] = react_services[0]
        for index, name in enumerate(django_services):
            routes["/api/" if index == 0 else f"/{name}/"] = name
    if not isinstance(routes, dict) or not routes:
        raise ValueError("ADDONS.apache.ROUTES must map URL paths to service names")
    lines = header + [
        "# Path routing is useful only when each target supports its configured",
        "# external prefix. Prefer VIRTUAL_HOSTS for Keycloak and mixed applications.",
        "ProxyRequests Off",
        "ProxyPreserveHost On",
        "AllowEncodedSlashes NoDecode",
        'RequestHeader set X-Forwarded-Proto "${APACHE_FORWARDED_PROTO}"',
        'RequestHeader set X-Forwarded-Port "${APACHE_FORWARDED_PORT}"',
        "LimitRequestBody ${APACHE_LIMIT_REQUEST_BODY}",
    ]
    for path, target in routes.items():
        target_name = str(target)
        route = str(path)
        if not route.startswith("/"):
            raise ValueError(f"Apache route must start with '/': {route!r}")
        port = target_port(target_name)
        lines += django_mount_aliases(target_name, route)
        lines += [
            f"ProxyPass {route} http://{target_name}:{port}/",
            f"ProxyPassReverse {route} http://{target_name}:{port}/",
            "ProxyTimeout 120",
            "TimeOut 120",
        ]
    return ("\n".join(lines) + "\n").encode()


def apache_log_configuration() -> bytes:
    return b'''# Shared Apache log formats and persistent log destinations.
ErrorLog "logs/apache_error.log"
LogLevel warn
LogFormat "%h %l %u %t \\"%r\\" %>s %b \\"%{Referer}i\\" \\"%{User-Agent}i\\"" combined
<IfModule logio_module>
    LogFormat "%v %{X-Forwarded-For}i %l %u %t \\"%r\\" %>s %b \\"%{Referer}i\\" \\"%{User-Agent}i\\" %D %I %O" proxy
</IfModule>
CustomLog "logs/apache.access.log" combined
'''


def apache_status_configuration() -> bytes:
    return b'''# Local-only operational endpoint; never expose it through ProxyPass.
ExtendedStatus On
<Location "/server-status">
    SetHandler server-status
    Require local
</Location>
'''


def compose_document(config: dict[str, Any], mode: str) -> tuple[bytes, list[tuple[Path, bytes]]]:
    services = normalized_services(config)
    addons = normalized_addons(config)
    service_lines = ["services:"]
    extra_lines: list[str] = []
    volume_lines: list[str] = []
    secret_lines: list[str] = []
    artifacts: list[tuple[Path, bytes]] = []
    for name, service in services.items():
        block, extras, volumes, secrets = compose_service_block(name, service, mode)
        service_lines += block
        extra_lines += extras
        volume_lines += volumes
        secret_lines += secrets

    if "apache" in addons:
        apache_options = addons["apache"]
        dependency_names = list(services)
        if "keycloak" in addons:
            dependency_names.append("keycloak")
        depends_on = "\n".join(
            f"      {name}:\n        condition: service_healthy"
            for name in dependency_names
        )
        apache_mounts: list[str] = []
        for name, service in services.items():
            if service["PROFILE"] != "django":
                continue
            static_volume = f"{name}_static" if mode == "prod" else f"{name}_test_static"
            if mode == "prod":
                documents_source = compose_variable(env_prefix(name), "HOST_DATA_PATH") + "/documents"
                documents_label = "Z"
            else:
                documents_source = f"{name}_test_documents"
                documents_label = "z"
            apache_mounts += [
                f"      - {static_volume}:/var/www/{name}/static:ro,z",
                f"      - {documents_source}:/var/www/{name}/documents:ro,{documents_label}",
            ]
        optional_mounts = apache_options.get("MOUNTS", [])
        if not isinstance(optional_mounts, list):
            raise ValueError("ADDONS.apache.MOUNTS must be a JSON array")
        apache_mounts += [f"      - {str(mount)}" for mount in optional_mounts]
        apache_template = TEMPLATES / "addons" / "apache" / "compose" / f"{mode}.service.yml.tmpl"
        apache_fragment = render(
            apache_template,
            {
                "APP_SLUG": str(config.get("APP_SLUG", "application")),
                "APACHE_DEPENDS_ON": depends_on,
                "APACHE_APPLICATION_MOUNTS": "\n".join(apache_mounts),
            },
        ).decode().rstrip("\n")
        service_lines += apache_fragment.splitlines()
        if mode == "test":
            volume_lines.append("  apache_test_logs:")
        artifacts += [
            (Path("deployment/apache/00-logs.conf"), apache_log_configuration()),
            (Path("deployment/apache/01-reverse-proxy.conf"), apache_proxy_configuration(services, apache_options)),
            (Path("deployment/apache/02-server-status.conf"), apache_status_configuration()),
        ]
    if "keycloak" in addons:
        keycloak_fragment = (
            TEMPLATES / "addons" / "keycloak" / "compose" / f"{mode}.service.yml.tmpl"
        ).read_text(encoding="utf-8").rstrip("\n")
        service_lines += keycloak_fragment.splitlines()
        volume_lines.append("  keycloak_db_data:")

    service_blocks = "\n".join(service_lines[1:] + extra_lines)
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
    return document, artifacts


def orchestrator_artifacts(config: dict[str, Any]) -> list[tuple[Path, bytes]]:
    normalized_services(config)
    addons = normalized_addons(config)
    prod, prod_extra = compose_document(config, "prod")
    test, test_extra = compose_document(config, "test")
    artifacts = [
        (Path("docker-compose.prod.yml"), prod),
        (Path("docker-compose.test.yml"), test),
        *prod_extra,
        *test_extra,
    ]
    for addon, options in addons.items():
        for mode, option_key in (
            ("production", "INSTALL_CONF"),
            ("test", "TEST_INSTALL_CONF"),
        ):
            configured_path = options.get(option_key)
            if not configured_path:
                continue
            relative = Path(str(configured_path))
            # External protected configurations belong to their owning repo or
            # operator storage and must never be written by this scaffold.
            if relative.is_absolute() or ".." in relative.parts:
                continue
            source = (
                TEMPLATES
                / "addons"
                / addon
                / "conf"
                / f"docker_{mode}_settings.txt.tmpl"
            )
            artifacts.append(
                (relative, render(source, {"APP_SLUG": str(config.get("APP_SLUG", "application"))}))
            )
    unique: dict[Path, bytes] = {}
    for path, content in artifacts:
        if path in unique and unique[path] != content:
            raise ValueError(f"Generated artifact {path} differs between modes")
        unique[path] = content
    return list(unique.items())


def bash_array(values: list[str]) -> str:
    return "(" + " ".join(shlex.quote(value) for value in values) + ")"


def orchestrator_template_values(config: dict[str, Any]) -> dict[str, str]:
    services = normalized_services(config)
    addons = normalized_addons(config)
    app_slug = str(config.get("APP_SLUG", "application"))
    names = list(services)
    permission_names = list(names)
    if "apache" in addons:
        permission_names.append("apache")
    if "keycloak" in addons:
        permission_names += ["keycloak_db", "keycloak"]
    configured_names = names + [
        name for name, options in addons.items() if options.get("INSTALL_CONF")
    ]

    default_conf_cases = []
    build_context_cases = []
    repo_path_cases = []
    install_path_cases = []
    readiness_cases = []
    image_cases = []
    profile_cases = []
    dockerfile_cases = []
    container_conf_cases = []
    uid_cases = []
    gid_cases = []
    settings_sources = []
    deployment_values = ['        "GIT_REVISION|$git_revision"']
    host_sources = []
    host_permissions = []
    running_cases = []
    bootstrap_cases = []
    smoke_checks = []
    smoke_profile_checks = []
    service_rows = []
    persistence_rows = []
    config_map_examples = []
    selected_profiles: list[str] = []

    for name, service in services.items():
        prefix = env_prefix(name)
        if service["PROFILE"] not in selected_profiles:
            selected_profiles.append(service["PROFILE"])
        service_rows.append(
            f"| `{name}` | `{service['PROFILE']}` | `{service['BUILD_CONTEXT']}` | `{service['APP_PORT']}` |"
        )
        config_map_examples.append(
            f"--install_conf_map {name},/protected/{name}_production_settings.txt"
        )
        quoted_name = shlex.quote(name)
        default_conf_cases.append(
            f"        {name}) [ \"$mode\" = test ] && echo {shlex.quote(service['TEST_INSTALL_CONF'])} || echo {shlex.quote(service['INSTALL_CONF'])} ;;"
        )
        build_context_cases.append(f"        {name}) echo {shlex.quote(service['BUILD_CONTEXT'])} ;;")
        repo_path = service.get("REPO_PATH", f"/srv/{name.replace('_', '-')}")
        repo_path_cases.append(f"        {name}) echo {shlex.quote(repo_path)} ;;")
        install_path = service.get("INSTALL_PATH", "/usr/share/nginx/html")
        install_path_cases.append(f"        {name}) echo {shlex.quote(install_path)} ;;")
        readiness = f"{install_path}/manage.py" if service["PROFILE"] == "django" else "/usr/share/nginx/html/index.html"
        readiness_cases.append(f"        {name}) echo {shlex.quote(readiness)} ;;")
        image_cases.append(f"        {name}) echo {shlex.quote(service['IMAGE'])} ;;")
        profile_cases.append(f"        {name}) echo {service['PROFILE']} ;;")
        dockerfile_cases.append(f"        {name}) echo {shlex.quote(service['DOCKERFILE'])} ;;")
        container_conf_cases.append(f"        {name}) echo {shlex.quote(service['CONTAINER_INSTALL_CONF'])} ;;")
        uid_cases.append(f"        {name}) config_value_or_default APP_UID \"${{install_conf_host_by_service[$1]}}\" {shlex.quote(service['APP_UID'])} ;;")
        gid_cases.append(f"        {name}) config_value_or_default APP_GID \"${{install_conf_host_by_service[$1]}}\" {shlex.quote(service['APP_GID'])} ;;")
        settings_sources.append(f'        "{prefix}|${{install_conf_host_by_service[{name}]}}"')
        deployment_values += [
            f'        "{prefix}_IMAGE|{service["IMAGE"]}"',
            f'        "{prefix}_INSTALL_CONF_PATH|${{install_conf_host_by_service[{name}]}}"',
        ]
        if service["PROFILE"] == "django":
            module = service["PROJECT_MODULE"]
            host_sources += [
                "    if [ \"$mode\" = production ]; then",
                f"        settings_output=\"$(config_value DJANGO_SETTINGS_PATH \"${{install_conf_host_by_service[{name}]}}\")\"",
                f"        mkdir -p \"$(dirname \"$settings_output\")\"",
                f"        prepare_django_settings_bind_mount {shlex.quote(service['BUILD_CONTEXT'] + '/conf/template_settings.py')} \"$settings_output\" \"${{install_conf_host_by_service[{name}]}}\"",
                "    fi",
            ]
            spec_name = re.sub(r"[^a-zA-Z0-9_]", "_", name) + "_host_bind_permission_spec"
            host_permissions += [
                f"    data_path=\"$(config_value HOST_DATA_PATH \"${{install_conf_host_by_service[{name}]}}\")\"",
                f"    log_path=\"$(config_value HOST_LOG_PATH \"${{install_conf_host_by_service[{name}]}}\")\"",
                f"    settings_path=\"$(config_value DJANGO_SETTINGS_PATH \"${{install_conf_host_by_service[{name}]}}\")\"",
                f"    uid=\"$(service_uid {quoted_name})\"; gid=\"$(service_gid {quoted_name})\"",
                f"    local -a {spec_name}=(",
                '        "$data_path/documents|$uid:$gid|0775"', '        "$log_path|$uid:$gid|0775"',
                '        "$(dirname "$settings_path")|-|0755"', '        "$settings_path|$uid:$gid|0664"', "    )",
                f'    apply_host_permission_spec "${{{spec_name}[@]}}"',
            ]
            running_cases += [
                f"        {name})",
                '            install_path="$(service_install_path "$service_name")"',
                '            uid="$(service_uid "$service_name")"; gid="$(service_gid "$service_name")"',
                f"            local -a {re.sub(r'[^a-zA-Z0-9_]', '_', name)}_running_mount_permission_spec=(",
                '                "$install_path/logs|$uid:$gid|u+rwX,g+rwX"',
                '                "$install_path/documents|$uid:$gid|u+rwX,g+rwX"',
                '                "$install_path/static|$uid:$gid|u+rwX,g+rwX,o+rX"', "            )",
                f'            apply_container_directory_permission_spec "$container_id" "${{{re.sub(r"[^a-zA-Z0-9_]", "_", name)}_running_mount_permission_spec[@]}}"',
                f'            prepare_django_container_settings_permissions "$container_id" "$install_path/{module}/settings.py" "$uid" "$gid"',
                "            ;;",
            ]
            bootstrap_cases += [
                f"        {name})",
                '            repo_path="$(service_repo_path "$service_name")"',
                f"            runtime_conf={shlex.quote(service['CONTAINER_INSTALL_CONF'])}",
                '            [[ "$runtime_conf" == /* ]] || runtime_conf="$repo_path/$runtime_conf"',
                '            uid="$(service_uid "$service_name")"; gid="$(service_gid "$service_name")"',
                '            stage_container_runtime_config "$container_id" "${install_conf_host_by_service[$service_name]}" "$runtime_conf" "$uid" "$gid"',
                '            args=(--bootstrap "$deployment_action" --git_revision "$git_revision" --conf "$runtime_conf" --skip_apache_restart)',
                '            for hook in "${migration_script_before[@]}"; do args+=(--script_before "$hook"); done',
                '            for hook in "${migration_script_after[@]}"; do args+=(--script_after "$hook"); done',
                '            status=0; engine_exec exec "$container_id" bash "$repo_path/install.sh" "${args[@]}" || status=$?',
                '            [ "$mode" = test ] || remove_container_runtime_config "$container_id" "$runtime_conf" || true',
                '            return "$status"', "            ;;",
            ]
            persistence_rows += [
                f"| `{name}` database | External production database | Database backup before migration |",
                f"| `{name}` documents | `HOST_DATA_PATH/documents` | Filesystem backup |",
                f"| `{name}` static | `{name}_static` named volume | Replaceable through collectstatic |",
            ]
            smoke_profile_checks += [
                f'    container_id="$(compose_run ps -q {shlex.quote(name)})"',
                f'    [ -n "$container_id" ] || fail "Service {name} has no container"',
                f'    compose_run exec -T {shlex.quote(name)} bash -lc {shlex.quote(f"cd {install_path} && source virtualenv/bin/activate && python manage.py check && ! python manage.py showmigrations --plan | grep -F \'[ ]\'")}',
                f'    echo "PASS: {name} Django checks and migrations"',
            ]
        else:
            running_cases += [f"        {name}) return 0 ;; # immutable React runtime"]
            bootstrap_cases += [f"        {name}) return 0 ;; # no runtime bootstrap"]
            persistence_rows.append(
                f"| `{name}` browser bundle | Immutable container image | Rebuild from recorded revision |"
            )
            smoke_profile_checks += [
                f'    compose_run exec -T {shlex.quote(name)} test -f /usr/share/nginx/html/index.html',
                f'    echo "PASS: {name} React/Vite bundle exists"',
            ]
        smoke_checks += [f'    check_url {shlex.quote(name)} "http://127.0.0.1:{service["APP_PORT"]}/health/"']

    for addon in addons:
        if addon == "apache":
            running_cases += [
                "        apache)",
                "            local -a apache_running_mount_permission_spec=()",
                '            apply_container_directory_permission_spec "$container_id" "${apache_running_mount_permission_spec[@]}"',
                "            ;;",
            ]
        elif addon == "keycloak":
            running_cases += [
                "        keycloak)",
                "            local -a keycloak_running_mount_permission_spec=()",
                '            apply_container_directory_permission_spec "$container_id" "${keycloak_running_mount_permission_spec[@]}"',
                "            ;;",
                "        keycloak_db)",
                "            local -a keycloak_db_running_mount_permission_spec=(",
                '                "/var/lib/mysql|999:999|u+rwX,g+rwX,o-rwx"',
                "            )",
                '            apply_container_directory_permission_spec "$container_id" "${keycloak_db_running_mount_permission_spec[@]}"',
                "            ;;",
            ]

    for addon, options in addons.items():
        if not options.get("INSTALL_CONF"):
            continue
        prefix = env_prefix(addon)
        default_conf_cases.append(
            f"        {addon}) [ \"$mode\" = test ] && echo {shlex.quote(str(options.get('TEST_INSTALL_CONF', options['INSTALL_CONF'])))} || echo {shlex.quote(str(options['INSTALL_CONF']))} ;;"
        )
        settings_sources.append(
            f'        "{prefix}|${{install_conf_host_by_service[{addon}]}}"'
        )
        deployment_values.append(
            f'        "{prefix}_INSTALL_CONF_PATH|${{install_conf_host_by_service[{addon}]}}"'
        )
        config_map_examples.append(
            f"--install_conf_map {addon},/protected/{addon}_production_settings.txt"
        )
        if addon == "apache":
            host_sources += [
                "    if [ \"$mode\" = production ]; then",
                f'        apache_log_path="$(config_value_or_default LOG_PATH "${{install_conf_host_by_service[apache]}}" "/var/log/local/{app_slug}/apache")"',
                '        mkdir -p "$script_dir/deployment/apache" "$apache_log_path"',
                "    fi",
            ]
            host_permissions += [
                f'    apache_log_path="$(config_value_or_default LOG_PATH "${{install_conf_host_by_service[apache]}}" "/var/log/local/{app_slug}/apache")"',
                "    local -a apache_host_bind_permission_spec=(",
                '        "$script_dir/deployment/apache|-|0755"',
                '        "$script_dir/deployment/apache/00-logs.conf|-|0644"',
                '        "$script_dir/deployment/apache/01-reverse-proxy.conf|-|0644"',
                '        "$script_dir/deployment/apache/02-server-status.conf|-|0644"',
                '        "$apache_log_path|-|0775"',
                "    )",
                '    apply_host_permission_spec "${apache_host_bind_permission_spec[@]}"',
            ]
        elif addon == "keycloak":
            host_sources += [
                '    keycloak_import_path="$(config_value_or_default IMPORT_PATH "${install_conf_host_by_service[keycloak]}" "$script_dir/keycloak/tmp-import")"',
                '    mkdir -p "$keycloak_import_path"',
                '    compgen -G "$keycloak_import_path/*.json" >/dev/null || { echo "Keycloak realm import JSON not found in $keycloak_import_path" >&2; return 1; }',
            ]
            host_permissions += [
                '    keycloak_import_path="$(config_value_or_default IMPORT_PATH "${install_conf_host_by_service[keycloak]}" "$script_dir/keycloak/tmp-import")"',
                "    local -a keycloak_host_bind_permission_spec=(",
                '        "$keycloak_import_path|-|0755"',
                "    )",
                '    for realm_file in "$keycloak_import_path"/*.json; do',
                '        keycloak_host_bind_permission_spec+=("$realm_file|-|0640")',
                "    done",
                '    apply_host_permission_spec "${keycloak_host_bind_permission_spec[@]}"',
            ]

    if "keycloak" in addons:
        persistence_rows.append(
            "| Keycloak database | `keycloak_db_data` MySQL named volume | Database and identity backup |"
        )

    profile_notes = []
    if "django" in selected_profiles:
        profile_notes.append(
            "- Django services build with an ephemeral settings secret, render protected host settings, and run controlled migration/bootstrap steps."
        )
    if "react-vite" in selected_profiles:
        profile_notes.append(
            "- React/Vite services use public build-time `VITE_*` configuration and an immutable, unprivileged Nginx runtime; they never run Django bootstrap."
        )
    addon_notes = []
    if "apache" in addons:
        addon_notes.append("- Apache generates either DNS virtual hosts from `ADDONS.apache.VIRTUAL_HOSTS` or prefix routes from `ADDONS.apache.ROUTES`.")
    if "keycloak" in addons:
        addon_notes.append("- Keycloak provides centralized identity with a health-checked MySQL service, realm import, and persistent database state.")
    return {
        "INSTALL_SERVICES_LITERAL": bash_array(names),
        "PERMISSION_SERVICES_LITERAL": bash_array(permission_names),
        "CONFIGURED_SERVICES_LITERAL": bash_array(configured_names),
        "DEFAULT_CONF_CASES": "\n".join(default_conf_cases),
        "BUILD_CONTEXT_CASES": "\n".join(build_context_cases),
        "REPO_PATH_CASES": "\n".join(repo_path_cases),
        "INSTALL_PATH_CASES": "\n".join(install_path_cases),
        "READINESS_CASES": "\n".join(readiness_cases),
        "IMAGE_CASES": "\n".join(image_cases),
        "PROFILE_CASES": "\n".join(profile_cases),
        "DOCKERFILE_CASES": "\n".join(dockerfile_cases),
        "CONTAINER_CONF_CASES": "\n".join(container_conf_cases),
        "UID_CASES": "\n".join(uid_cases),
        "GID_CASES": "\n".join(gid_cases),
        "SETTINGS_SOURCES": "\n".join(settings_sources),
        "DEPLOYMENT_VALUES": "\n".join(deployment_values),
        "PREPARE_HOST_SOURCES": "\n".join(host_sources) or "    return 0",
        "HOST_PERMISSION_SPECS": "\n".join(host_permissions) or "    return 0",
        "RUNNING_PERMISSION_CASES": "\n".join(running_cases),
        "BOOTSTRAP_CASES": "\n".join(bootstrap_cases),
        "SMOKE_CHECKS": "\n".join(smoke_checks),
        "SMOKE_PROFILE_CHECKS": "\n".join(smoke_profile_checks),
        "SERVICE_INVENTORY_ROWS": "\n".join(service_rows),
        "PROFILE_DOCUMENTATION": "\n".join(profile_notes) or "- No framework profile selected.",
        "ADDON_DOCUMENTATION": "\n".join(addon_notes) or "- No optional add-ons selected.",
        "PERSISTENCE_ROWS": "\n".join(persistence_rows) or "| None | Immutable image | Rebuild |",
        "CONFIG_MAP_EXAMPLES": " ".join(config_map_examples),
    }


def deployment_shape(config: dict[str, Any]) -> str:
    if owns_profile_artifacts(config):
        return f"profile:{selected_profile(config)}"
    return "multi-service"


def synchronize(target: Path, config: dict[str, Any], initial: bool) -> int:
    state = load_state(target)
    if not uses_service_descriptor(config) and (initial or not state.get("files")):
        raise ValueError(
            "New projects must use the canonical SERVICES descriptor; "
            "top-level PROFILE is supported only when synchronizing old state"
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
        if uses_service_descriptor(config):
            owned_name, _ = owned_profile_service(config) or ("", {})
            render_values.update(normalized_services(config)[owned_name])
        else:
            render_values.update(next(iter(normalized_services(config).values())))
    render_values.update(orchestrator_template_values(config))
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
