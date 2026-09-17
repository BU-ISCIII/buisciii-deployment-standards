#!/usr/bin/env python3
"""Cross-check generated deployment wiring before images are built.

This file is centrally managed. Applications must not edit vendored copies.

`container_install.sh` calls this checker after Compose validation. It reads
only generated artifacts: the protected Compose environment file, the Compose
file and, when the Apache add-on is selected, the rendered Apache
configuration. Each finding names a rule and the setting to change. Values
are printed only for URL and host settings, never for other settings.

Rules:
  unresolved-placeholder  a CHANGE_ME marker remains in a setting
  unknown-host            an internal URL or DB_HOST names no Compose service
  upstream-port           an internal URL port differs from the target's port
  loopback-target         a server-side proxy target points at the container itself
  database-host           DB_HOST ignores the Compose-managed database service
  django-hostname         a host name with underscores reaches Django
  allowed-hosts           a host reaching Django is missing from ALLOWED_HOSTS
  keycloak-url            an OIDC issuer or JWKS URL is malformed
  keycloak-origin         Keycloak public URLs disagree across settings
  keycloak-realm          Keycloak realms disagree across settings
  canonical-url           AUTH_URL and NEXTAUTH_URL disagree

Production findings are errors and fail the installation. Test findings are
reported as warnings because test settings intentionally use shortcuts.
Findings the checker cannot confirm (for example a single-label host that may
resolve through institutional DNS) are always warnings.
"""

from __future__ import annotations

import argparse
import ipaddress
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


PLACEHOLDER = "CHANGE_ME"
URL = re.compile(r"https?://[^\s,;'\"<>]+")
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEFAULT_PORTS = {"http": 80, "https": 443}
ISSUER_PATH = re.compile(r"^(?:/auth)?/realms/([^/]+)/?$")
JWKS_PATH = re.compile(r"^(?:/auth)?/realms/([^/]+)/protocol/openid-connect/certs/?$")
KEYCLOAK_ORIGIN_SUFFIXES = (
    "KEYCLOAK_URL",
    "KEYCLOAK_PUBLIC_URL",
    "KEYCLOAK_ADMIN_API_BASE_URL",
)
KEYCLOAK_REALM_SUFFIXES = ("KEYCLOAK_REALM", "KEYCLOAK_ADMIN_API_REALM")
# Server-side Keycloak calls may use an internal route instead of the public URL.
KEYCLOAK_SERVER_SIDE_SUFFIXES = ("OIDC_JWKS_URL", "KEYCLOAK_ADMIN_API_BASE_URL")


@dataclass
class Finding:
    rule: str
    message: str
    confirmed: bool = True


@dataclass
class ComposeService:
    name: str
    names: set[str] = field(default_factory=set)
    ports: set[int] = field(default_factory=set)


@dataclass
class ApacheRoute:
    source: str
    server_names: list[str]
    preserve_host: bool
    target: str


def env_prefix(service_name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", service_name.upper())


def normalized_name(name: str) -> str:
    return re.sub(r"[_.]", "-", name.lower())


def read_environment(path: Path) -> dict[str, str]:
    """Read the dotenv file written by write_compose_environment_file."""
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        if len(raw) >= 2 and raw[0] == raw[-1] == "'":
            raw = raw[1:-1].replace("\\'", "'")
        values[key.strip()] = raw
    return values


def yaml_scalar(text: str) -> str:
    return text.split(" #", 1)[0].strip().strip("\"'")


def read_compose_services(path: Path) -> dict[str, ComposeService]:
    """Read service names, network aliases, container names and exposed ports.

    Generated Compose files use conventional block indentation, so a small
    line scanner is sufficient and keeps the checker free of YAML packages.
    """
    services: dict[str, ComposeService] = {}
    in_services = False
    current: ComposeService | None = None
    list_key = ""

    def add(key: str, value: str) -> None:
        if current is None or not value or "$" in value:
            return
        if key == "expose":
            match = re.match(r"(\d+)", value)
            if match:
                current.ports.add(int(match.group(1)))
        else:
            current.names.add(value.lower())

    for raw in path.read_text().splitlines():
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0:
            in_services = text == "services:"
            current = None
            continue
        if not in_services:
            continue
        service_match = re.fullmatch(r"[\"']?([A-Za-z0-9._-]+)[\"']?:", text)
        if indent == 2 and service_match:
            name = service_match.group(1)
            current = services.setdefault(name, ComposeService(name, {name.lower()}))
            list_key = ""
            continue
        if current is None:
            continue
        if text.startswith("-"):
            if list_key:
                add(list_key, yaml_scalar(text[1:]))
            continue
        key_match = re.match(r"([A-Za-z0-9_]+):\s*(.*)$", text)
        if not key_match:
            continue
        key, rest = key_match.group(1), key_match.group(2)
        list_key = ""
        if key == "container_name":
            add(key, yaml_scalar(rest))
        elif key in {"aliases", "expose"}:
            if rest.startswith("["):
                for item in rest.strip("[]").split(","):
                    add(key, yaml_scalar(item))
            elif not rest:
                list_key = key
    return services


def read_apache_routes(directory: Path) -> list[ApacheRoute]:
    """Read ProxyPass targets and the host names forwarded to them."""
    routes: list[ApacheRoute] = []
    for conf in sorted(directory.glob("*.conf")):
        server_names: list[str] = []
        preserve_host = False
        pending: list[tuple[int, str]] = []
        for number, raw in enumerate(conf.read_text().splitlines(), start=1):
            text = raw.strip()
            if not text or text.startswith("#"):
                continue
            words = text.split()
            directive = words[0].lower()
            if directive.startswith("<virtualhost"):
                server_names, preserve_host, pending = [], False, []
            elif directive in {"servername", "serveralias"}:
                server_names.extend(words[1:])
            elif directive == "proxypreservehost" and len(words) > 1:
                preserve_host = words[1].lower() == "on"
            elif directive == "proxypass" and len(words) > 2 and words[2] != "!":
                pending.append((number, words[2]))
            elif directive == "</virtualhost>":
                for line_number, target in pending:
                    routes.append(ApacheRoute(
                        f"{conf.name}:{line_number}", list(server_names),
                        preserve_host, target,
                    ))
                pending = []
    return routes


def is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def display_url(url: str) -> str:
    """Remove credentials before a URL is printed."""
    parts = urlsplit(url)
    if parts.username is None and parts.password is None:
        return url
    return url.replace(parts.netloc, parts.netloc.rsplit("@", 1)[-1], 1)


def host_name(value: str) -> str:
    """Return the bare host of an Apache ServerName or Host-like value."""
    value = value.strip().lower()
    if "://" in value:
        value = urlsplit(value).hostname or ""
    if value.startswith("["):
        return value
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


def origin(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        port = None
    suffix = "" if port in (None, DEFAULT_PORTS.get(parts.scheme)) else f":{port}"
    return f"{parts.scheme.lower()}://{host}{suffix}"


def django_host_allowed(host: str, patterns: list[str]) -> bool:
    """Mirror django.http.request.validate_host for ALLOWED_HOSTS matching."""
    host = host.rstrip(".").lower()
    for pattern in patterns:
        pattern = pattern.lower()
        if pattern == "*" or pattern == host:
            return True
        if pattern.startswith(".") and (host.endswith(pattern) or host == pattern[1:]):
            return True
    return False


class Topology:
    def __init__(
        self,
        environment: dict[str, str],
        compose: dict[str, ComposeService],
        profiles: dict[str, str],
    ) -> None:
        self.environment = environment
        self.compose = compose
        self.profiles = profiles
        for name in profiles:
            port = environment.get(f"{env_prefix(name)}_APP_PORT", "")
            if name in compose and port.isdigit():
                # The settings-owned APP_PORT is the service's only listener.
                compose[name].ports = {int(port)}

    def resolve(self, host: str) -> ComposeService | None:
        host = host.lower()
        for service in self.compose.values():
            if host in service.names:
                return service
        return None

    def suggestion(self, host: str) -> str:
        wanted = normalized_name(host)
        for service in self.compose.values():
            if any(normalized_name(name) == wanted for name in service.names):
                return service.name
        return ""

    def is_internal(self, host: str) -> bool:
        host = host.lower()
        return (
            host in LOOPBACK_HOSTS or host == "host.docker.internal"
            or self.resolve(host) is not None
        )

    def is_django(self, service: ComposeService) -> bool:
        return self.profiles.get(service.name) == "django"


def internal_host_findings(
    topology: Topology, label: str, url: str, parts, host: str
) -> tuple[ComposeService | None, list[Finding]]:
    """Resolve an internal URL host and validate its port."""
    findings: list[Finding] = []
    service = topology.resolve(host)
    port_target = service
    if service is None:
        if "." in host or host in LOOPBACK_HOSTS or is_ip(host):
            return None, findings
        suggestion = topology.suggestion(host)
        if suggestion:
            findings.append(Finding(
                "unknown-host",
                f"{label}={display_url(url)!r}: host {host!r} is not a Compose "
                f"service; did you mean {suggestion!r}?",
            ))
            # Also report a wrong port now so both fixes happen in one run.
            port_target = topology.compose[suggestion]
        else:
            findings.append(Finding(
                "unknown-host",
                f"{label}={display_url(url)!r}: host {host!r} is not a Compose "
                "service; confirm it resolves from inside the containers",
                confirmed=False,
            ))
            return None, findings
    try:
        port = parts.port or DEFAULT_PORTS.get(parts.scheme)
    except ValueError:
        return service, findings
    if port_target is not None and port_target.ports and port not in port_target.ports:
        expected = ", ".join(str(item) for item in sorted(port_target.ports))
        findings.append(Finding(
            "upstream-port",
            f"{label}={display_url(url)!r}: {port_target.name} listens on {expected}, "
            f"not {port}",
        ))
    return service, findings


def check_placeholders(topology: Topology) -> list[Finding]:
    keys = sorted(key for key, value in topology.environment.items() if PLACEHOLDER in value)
    return [
        Finding("unresolved-placeholder", f"{key} still contains {PLACEHOLDER}")
        for key in keys
    ]


def check_internal_urls(
    topology: Topology, routes: list[ApacheRoute]
) -> tuple[list[Finding], dict[str, list[tuple[str, str]]]]:
    """Validate every internal URL and record the Host each Django service receives."""
    findings: list[Finding] = []
    arrivals: dict[str, list[tuple[str, str]]] = {}

    for key, value in sorted(topology.environment.items()):
        if PLACEHOLDER in value:
            continue
        for url in URL.findall(value):
            parts = urlsplit(url)
            host = (parts.hostname or "").lower()
            if not host or "$" in url:
                continue
            if key.endswith("PROXY_TARGET") and host in LOOPBACK_HOSTS:
                findings.append(Finding(
                    "loopback-target",
                    f"{key}={display_url(url)!r}: inside a container {host} is the "
                    "calling container itself; use the Compose service name",
                ))
                continue
            service, url_findings = internal_host_findings(topology, key, url, parts, host)
            findings.extend(url_findings)
            if service is not None and topology.is_django(service):
                arrivals.setdefault(service.name, []).append((host, key))

    for route in routes:
        parts = urlsplit(route.target)
        host = (parts.hostname or "").lower()
        if not host or "$" in route.target:
            continue
        label = f"Apache ProxyPass {route.source}"
        service, url_findings = internal_host_findings(
            topology, label, route.target, parts, host
        )
        findings.extend(url_findings)
        if service is None or not topology.is_django(service):
            continue
        if route.preserve_host:
            for name in route.server_names:
                arrivals.setdefault(service.name, []).append(
                    (host_name(name), f"{label} ServerName (ProxyPreserveHost On)")
                )
        else:
            arrivals.setdefault(service.name, []).append((host, label))
    return findings, arrivals


def check_django_hosts(
    topology: Topology, arrivals: dict[str, list[tuple[str, str]]]
) -> list[Finding]:
    findings: list[Finding] = []
    for service_name, hosts in sorted(arrivals.items()):
        allowed_key = f"{env_prefix(service_name)}_DJANGO_ALLOWED_HOSTS"
        allowed_value = topology.environment.get(allowed_key)
        patterns = [
            item.strip() for item in (allowed_value or "").split(",") if item.strip()
        ]
        for host, source in dict.fromkeys(hosts):
            if not host or "*" in host or "$" in host:
                continue
            if "_" in host:
                findings.append(Finding(
                    "django-hostname",
                    f"{source}: Django rejects the Host {host!r} sent to "
                    f"{service_name} because it contains an underscore; use a "
                    "hyphenated service name or network alias",
                ))
            elif allowed_value is not None and PLACEHOLDER not in allowed_value \
                    and not django_host_allowed(host, patterns):
                findings.append(Finding(
                    "allowed-hosts",
                    f"{source}: {service_name} receives Host {host!r}, which "
                    f"{allowed_key} does not allow",
                ))
    return findings


def check_databases(topology: Topology) -> list[Finding]:
    findings: list[Finding] = []
    for service_name, profile in topology.profiles.items():
        if profile != "django":
            continue
        key = f"{env_prefix(service_name)}_DB_HOST"
        host = topology.environment.get(key, "").strip().lower()
        if not host or PLACEHOLDER in host:
            continue
        managed = sorted(
            name for name in topology.compose
            if normalized_name(name) == f"{normalized_name(service_name)}-db"
        )
        resolved = topology.resolve(host)
        if host in LOOPBACK_HOSTS:
            findings.append(Finding(
                "database-host",
                f"{key}={host!r}: inside a container {host} is the application "
                "container itself",
            ))
        elif managed and (resolved is None or resolved.name not in managed):
            findings.append(Finding(
                "database-host",
                f"{key}={host!r}: Compose manages the database service "
                f"{managed[0]!r} for {service_name}; use DB_HOST={managed[0]!r} "
                "or remove that service for an external database",
            ))
        elif resolved is None and "." not in host and not is_ip(host):
            suggestion = topology.suggestion(host)
            findings.append(Finding(
                "unknown-host",
                f"{key}={host!r} is not a Compose service"
                + (f"; did you mean {suggestion!r}?" if suggestion
                   else "; confirm it resolves from inside the containers"),
                confirmed=bool(suggestion),
            ))
    return findings


def check_keycloak(topology: Topology) -> list[Finding]:
    findings: list[Finding] = []
    origins: dict[str, list[str]] = {}
    realms: dict[str, list[str]] = {}

    for key, value in sorted(topology.environment.items()):
        value = value.strip()
        if not value or PLACEHOLDER in value:
            continue
        issuer = key.endswith("OIDC_ISSUER")
        jwks = key.endswith("OIDC_JWKS_URL")
        if issuer or jwks:
            parts = urlsplit(value)
            match = (ISSUER_PATH if issuer else JWKS_PATH).match(parts.path)
            if not parts.hostname or not match:
                expected = (
                    "<keycloak-url>/realms/<realm>" if issuer
                    else "<keycloak-url>/realms/<realm>/protocol/openid-connect/certs"
                )
                findings.append(Finding(
                    "keycloak-url",
                    f"{key}={display_url(value)!r} does not match {expected}",
                ))
                continue
            realms.setdefault(match.group(1), []).append(key)
            if not (jwks and topology.is_internal(parts.hostname)):
                origins.setdefault(origin(value), []).append(key)
        elif key.endswith(KEYCLOAK_ORIGIN_SUFFIXES):
            parts = urlsplit(value)
            server_side = key.endswith(KEYCLOAK_SERVER_SIDE_SUFFIXES)
            if parts.hostname and not (server_side and topology.is_internal(parts.hostname)):
                origins.setdefault(origin(value), []).append(key)
        elif key.endswith(KEYCLOAK_REALM_SUFFIXES):
            realms.setdefault(value, []).append(key)

    def disagreement(values: dict[str, list[str]]) -> str:
        return "; ".join(
            f"{value!r} in {', '.join(keys)}" for value, keys in sorted(values.items())
        )

    if len(origins) > 1:
        findings.append(Finding(
            "keycloak-origin",
            "Keycloak public URLs must share one origin: " + disagreement(origins),
        ))
    if len(realms) > 1:
        findings.append(Finding(
            "keycloak-realm",
            "Keycloak realm must be identical everywhere: " + disagreement(realms),
        ))
    return findings


def check_canonical_urls(topology: Topology) -> list[Finding]:
    findings: list[Finding] = []
    for key, value in sorted(topology.environment.items()):
        if not key.endswith("NEXTAUTH_URL"):
            continue
        auth_key = key[: -len("NEXTAUTH_URL")] + "AUTH_URL"
        auth_value = topology.environment.get(auth_key, "")
        if not value or not auth_value or PLACEHOLDER in value + auth_value:
            continue
        if value.rstrip("/") != auth_value.rstrip("/"):
            findings.append(Finding(
                "canonical-url",
                f"{auth_key}={auth_value!r} and {key}={value!r} must be identical",
            ))
    return findings


def run_checks(
    environment: dict[str, str],
    compose: dict[str, ComposeService],
    profiles: dict[str, str],
    routes: list[ApacheRoute],
    mode: str,
) -> list[Finding]:
    topology = Topology(environment, compose, profiles)
    findings: list[Finding] = []
    if mode == "production":
        findings.extend(check_placeholders(topology))
    url_findings, arrivals = check_internal_urls(topology, routes)
    findings.extend(url_findings)
    findings.extend(check_django_hosts(topology, arrivals))
    if mode == "production":
        # Test Compose files set DB_HOST to the generated test database directly.
        findings.extend(check_databases(topology))
    findings.extend(check_keycloak(topology))
    findings.extend(check_canonical_urls(topology))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--mode", choices=("production", "test"), required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--compose-file", type=Path, required=True)
    parser.add_argument("--apache-config-dir", type=Path)
    parser.add_argument(
        "--service", action="append", default=[], metavar="NAME=PROFILE",
        help="Application service and its profile; repeat for every service.",
    )
    args = parser.parse_args()

    profiles: dict[str, str] = {}
    for entry in args.service:
        name, separator, profile = entry.partition("=")
        if not separator or not name or not profile:
            parser.error(f"invalid --service {entry!r}; expected NAME=PROFILE")
        profiles[name] = profile

    environment = read_environment(args.env_file)
    compose = read_compose_services(args.compose_file)
    routes = []
    if args.apache_config_dir and args.apache_config_dir.is_dir():
        routes = read_apache_routes(args.apache_config_dir)

    findings = run_checks(environment, compose, profiles, routes, args.mode)
    errors = [
        finding for finding in findings
        if finding.confirmed and args.mode == "production"
    ]
    for finding in findings:
        level = "ERROR" if finding in errors else "WARNING"
        print(f"{level} [{finding.rule}] {finding.message}")
    print(
        f"Deployment configuration check ({args.mode}): "
        f"{len(errors)} error(s), {len(findings) - len(errors)} warning(s)."
    )
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
