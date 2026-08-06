# RELECOV container installer function audit

This audit covers the functions still defined by `container_install.sh` after
extracting the synchronized `common.sh` and `django.sh` libraries.

## Ownership rule

The outer `container_install.sh` owns host and Compose orchestration. The inner
`install.sh` owns application staging and bootstrap inside the container.
Django settings rendering therefore belongs to the outer layer: the host file
used as a bind-mount source must exist before Compose creates the container.
It is implemented in the shared Django profile so applications do not duplicate
that host-side lifecycle.

## Functions moved now

| Previous application function | Shared function | Reason |
| --- | --- | --- |
| `normalize_settings_bind_path` | `normalize_bind_file_path` | Same path rule; default path remains an argument. |
| `render_django_settings_file` | Django profile function of the same name | Same standard settings keys and secret preservation. |
| `prepare_django_settings_bind_mount` | Django profile function of the same name | Same pre-Compose host lifecycle. |
| local config precedence helpers | `config_value_or_default` | Identical environment, config, default precedence. |
| temporary configuration deletion | `cleanup_files` | Generic and safely limited to named files. |
| legacy stale-container cleanup | Removed | New deployments rely on Compose naming and lifecycle instead of deleting explicitly named Podman containers. |

## Functions remaining in relecov-platform

| Function | Decision | Why / required refactor |
| --- | --- | --- |
| `usage` | Keep | Application examples and supported deployment topology. |
| `cleanup_temp_confs` | Keep thin callback | `trap` needs a no-argument app callback; deletion is shared. |
| `config_value_for_service` | Keep thin adapter | Selects the service-specific config map, then calls the shared precedence helper. |
| `render_apache_config` | Keep thin adapter | Placeholder values are topology-specific; rendering and safe file installation now use `render_config_template`. |
| `write_compose_env_file` | Keep | Its variables are the public contract of this Compose topology. A generic writer could hide missing required keys. |
| `default_service_install_conf` | Keep | Application service/default mapping. |
| `service_build_context_dir` | Keep | Monorepo/sibling-repository topology. |
| `service_is_install_target` | Removed | Platform now uses the shared exact-match `array_contains` helper directly. |
| `prepare_service_conf` | Keep thin adapter | Shared validation/staging returns explicit paths; this adapter applies Platform service context, override, and default-install-path callbacks. |
| `service_container_name` | Keep callback | Explicit legacy names are application-specific and consumed by the shared resolver. |
| `service_repo_path` | Keep | Container source layout differs by service. |
| `service_install_path` | Keep | Reads this application's per-service state. |
| `compose_service_image_id` | Moved | Now shared with compose file and service supplied explicitly. |
| four diagnostic functions | Moved | Stateless repository, image, and container diagnostics now receive all paths, IDs, and expected revisions explicitly. |
| `prepare_service_mount_permissions` | Keep | Directory set and Django package path are application/service policy. |
| `prepare_host_bind_mount_permissions` | Refactor candidate | Permission mechanics are shared, but paths, owners, and Apache files need a declarative mount specification. |
| `prepare_apache_bind_mounts` | Keep orchestrator | Defines which application templates and destinations must exist before Compose starts. |

## Functions remaining in relecov-iskylims

| Function | Decision | Why / required refactor |
| --- | --- | --- |
| `usage` | Keep | Application documentation and examples. |
| `cleanup_temp_conf` | Keep thin callback | `trap` adapter only; deletion is shared. |
| `render_apache_config` | Keep thin adapter | Supplies application placeholders and values to shared `render_config_template`. |
| `write_compose_env_file` | Keep | Defines the exact iSkyLIMS Compose interpolation interface. |
| `service_container_name` | Keep callback | Legacy explicit names are application-specific. |
| `resolve_app_container`, `try_resolve_app_container`, `ensure_app_running` | Removed | Call sites now use the shared resolver directly and assign the resolved ID explicitly. |
| four diagnostic functions | Moved | Both applications now use the same stateless shared diagnostic API. |
| `prepare_app_mount_permissions` | Keep | Encodes iSkyLIMS writable paths and settings package. |
| `prepare_host_bind_mount_permissions` | Refactor candidate | Requires a declarative list of host path, owner, and mode tuples. |

## Recommended next extraction

Refactor in the following order and review each item separately:

1. **Django secret generation — completed.** Move
   `generate_django_secret_key` from `common.sh` to `django.sh`; it has one
   framework-specific consumer and no application state.
2. **Compose image lookup — completed.** `compose_service_image_id` now lives in
   `common.sh` with compose file and service as explicit arguments.
3. **iSkyLIMS resolver wrappers — completed.** The three scalar-state adapters
   were removed; call sites now use the shared resolver directly.
4. **Source/image diagnostics — completed.** Stateless shared functions now
   accept repository paths, image IDs/names, container IDs, and expected
   revisions; wrapper-specific scalar/array implementations were removed.
5. **Array membership — completed.** Platform service-target validation now
   uses the shared exact-match `array_contains` helper, including empty-array
   behavior.
6. **Configuration staging — completed.** Shared validation and temporary
   build-context preparation now return named host, relative, and temporary
   paths. Platform callbacks retain service context, override, and default
   install-path policy; iSkyLIMS calls the shared operation directly.
7. **Django mounted-file permissions — completed.** Settings ownership/mode now
   lives in `django.sh`, parameterized by container, path, UID, and GID;
   application writable-directory policy remains in each wrapper.
8. **Host permission specification — completed.** Each wrapper owns a
   declarative `path|owner|mode` list, while the tested shared helper validates
   entries, skips absent optional paths, and applies Docker/Podman-compatible
   ownership and modes.
9. **Deployment verification and runtime configuration — completed.** Compose
   path/model validation, protected runtime configuration staging/removal,
   combined pre-build diagnostics, and standardized smoke-test invocation now
   use stateless shared helpers. Their lifecycle call sites remain visible in
   each application wrapper.

Do not move `usage`, Compose environment contents, service/path mappings,
Apache token mappings, or application writable-directory lists. Those express
the deployment topology rather than reusable mechanics. Permission functions
remain last because a shared mistake could change production ownership on
application-specific paths.

## Regeneration target

After the shared extractions above stabilize, both RELECOV wrappers can be
regenerated from one `container_install.sh` template. The generated script
should contain the canonical CLI and lifecycle plus a clearly marked
**application customization section**. No separate `application.sh` is needed.
That in-script section provides declarations and documented function
placeholders for:

- service names and install order;
- build contexts and stable image tags;
- container, source, installation, and settings paths;
- test and production configuration defaults;
- Apache template/token mappings;
- persistent path ownership/mode specifications;
- optional demo-data and post-bootstrap hooks.

The template MUST work for one service or an ordered service array. Each custom
function placeholder MUST have a safe no-op default, document its arguments and
return contract, and show where developers add application code. The generic
lifecycle calls those hooks without containing application names or paths.

The scaffold currently assumes one service and uses different internal variable
names from the RELECOV wrappers. Do not replace either working wrapper from that
template yet. First convert the template to the same shared-library API and a
multi-service data model; then generate candidates and compare their observable
CLI, Compose commands, bootstrap order, mounts, and smoke tests before replacing
the existing scripts.
