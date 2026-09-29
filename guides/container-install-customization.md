# Container installer customization

How application maintainers customize generated `container_install.sh` behavior
within its supported extension points. For exact shared functions, see the
[container installer reference](../reference/scripts/container-install.md).

> **Status:** Documentation outline. Detailed guidance will be added incrementally.

## Future sections

- Purpose of `container_install.sh`
- Shared/common and application-specific behavior
- Allowed customization points
- Docker and rootless Podman compatibility
- User namespaces and permission handling
- SELinux
- Application service arrays and bootstrap callbacks
- Persistent paths and readiness
- Security rationale
