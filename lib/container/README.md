# Shared container installer library

`common.sh` contains application-neutral functions used by
`container_install.sh`. `django.sh` contains the reusable Django profile for
creating a settings bind source on the host before Compose starts. Vendored
copies live under `deployment/lib/container/` in application repositories.

Applications MUST NOT edit vendored library files. Application-specific behavior
belongs in the wrapper `container_install.sh` or another application-owned
library.

## Required globals

The wrapper sets these before calling the relevant functions:

| Variable | Used by |
|---|---|
| `engine` | Engine selection and Podman fallbacks |
| `ENGINE_CMD`, `COMPOSE_CMD` | Populated by `set_engine` |
| `mode` | `compose_with_env_exec` |
| `compose_env_file` | `compose_with_env_exec` |
| `compose_file` | `service_exists` |

The wrapper MAY implement `service_container_name <service>` for legacy
explicit container names. Otherwise container resolution uses Compose labels.

## Public functions

- `set_engine`
- `engine_exec`
- `engine_build`
- `compose_exec`
- `compose_with_env_exec`
- `compose_service_image_id`
- `require_compose_file`
- `validate_compose_configuration`
- `repository_revision`
- `print_repository_diagnostics`
- `print_image_before_diagnostics`
- `print_image_after_diagnostics`
- `print_prebuild_diagnostics`
- `print_container_repository_diagnostics`
- `copy_with_podman_fallback`
- `chmod_with_podman_fallback`
- `chown_with_podman_fallback`
- `apply_host_permission_spec`
- `apply_container_directory_permission_spec`
- `stage_container_runtime_config`
- `remove_container_runtime_config`
- `run_standard_smoke_test`
- `normalize_apache_server_name`
- `sed_replacement_escape`
- `sed_search_escape`
- `read_install_conf_value`
- `read_install_conf_first`
- `config_value_or_default`
- `normalize_bind_file_path`
- `render_config_template`
- `compose_environment_quote`
- `write_compose_environment_file`
- `prepare_install_configuration`
- `cleanup_files`
- `array_contains`
- `service_exists`
- `resolve_service_container`
- `ensure_service_running`

Host permission policy remains application-owned and is expressed as an array
of `path|owner|mode` entries. A `-` preserves the current owner or mode, and
missing optional paths are skipped. The wrapper passes that array to
`apply_host_permission_spec`; the shared library owns only iteration and the
Docker/Podman-compatible operations.

Writable directory mounts are declared separately inside the application
wrapper as `path|owner|mode` entries and passed, with a resolved container ID,
to `apply_container_directory_permission_spec`. That helper creates each
directory and applies ownership/mode recursively from inside the running
container. Include named-volume destinations and writable bind destinations;
exclude read-only mounts and ordinary immutable application source. Mounted
files such as Django settings use their file-specific profile helper instead.

Compose interpolation files are generated with
`write_compose_environment_file <output> <sources-array-name>
<values-array-name>`. Source entries use `PREFIX|settings-path`; an empty prefix
keeps standalone setting names, while orchestrators use prefixes such as
`PLATFORM` and `ISKYLIMS`. Explicit `KEY|value` entries are reserved for values
not stored in application settings, such as image tags and the requested Git
revision. The writer normalizes shell-quoted settings, rejects duplicates and
multiline values, and atomically installs the result with mode `0600`.

The Django profile adds:

- `generate_django_secret_key`
- `render_django_settings_file`
- `prepare_django_settings_bind_mount`
- `prepare_django_container_settings_permissions`

These are outer-installer functions even though they render Django settings.
The settings file is a host bind-mount source and must exist before container
creation; the in-container `install.sh` runs too late to establish that source.

Changes to function names, arguments, output, or return behavior require a
library version change and a semantic deployment change package.
