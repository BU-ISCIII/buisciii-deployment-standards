# Container installer customization

`container_install.sh` is the host-side entry point for a generated deployment. Most of it is standard-managed. Application code belongs only in the marked application block.

For the exact command-line interface and lifecycle, see the [container installer reference](../reference/scripts/container-install.md).

## What the installer does

At a high level, the generated installer:

1. parses and validates options;
2. resolves test or production configuration;
3. selects Docker or Podman;
4. prepares host files and bind-mount permissions;
5. validates the rendered Compose model;
6. performs permission-only repair when requested;
7. builds images;
8. recreates and starts the topology;
9. waits for application readiness;
10. repairs mounts inside running containers;
11. runs profile bootstrap;
12. optionally loads application test or demo data; and
13. runs the generated smoke test.

The lifecycle order, service arrays, configuration lookup, readiness, builds, bootstrap, and smoke dispatch are generated behavior. Do not edit them for one application.

## What you may customize

The only application-owned section in the generated script is:

```text
# BEGIN BU-ISCIII APPLICATION: deployment-hooks
...
# END BU-ISCIII APPLICATION: deployment-hooks
```

Scaffold `check` and `sync` preserve content inside this block. Changes outside it are managed drift.

**After every modification inside this block, run `refresh-state` before `sync`, then run `check` and commit the customization together with `state.json`.** Follow this sequence even when you do not know whether the standard changed. Whole-file checksum comparisons can otherwise report `managed-drift-with-update` for a supported custom edit combined with a standard update. See the [scaffold workflow](scaffold-workflow.md#refresh-after-editing-supported-custom-blocks) for commands, a demo-data hook example, and older state files.

The block currently exposes exactly these application contracts:

```bash
application_supports_test_data=false

load_test_deployment_data() {
    ...
}

set_application_host_bind_permissions() {
    ...
}

set_application_running_mount_permissions() {
    ...
}
```

Use them only for behavior unique to the application and not representable by the project descriptor, installation settings, a profile, an addon, or a reusable shared helper.

Functions elsewhere in the generated script are not customization points merely because they are shell functions. Service lookup, readiness, production build, profile bootstrap, and profile/addon permission cases are generated from their owning templates.

## Test and demo data

Set `application_supports_test_data=true` only when `load_test_deployment_data` implements the contract.

The hook is called with:

```text
$1  selected application service name
$2  validated absolute demo-data path, or an empty string for default test data
```

The current globals `skip_test_data` and `skip_demo_data` tell the hook which application-owned imports to omit. Use `current_service_container` to resolve the target container and `engine_exec` for engine-neutral container commands.

On a fresh test install, the hook receives the first install service and an empty path so it can load its safe default fixtures. A multi-service application must dispatch its own defaults inside the hook. The `--skip_test_data_service` option can suppress defaults for the selected service.

An explicit `--demo_data_map service,path` calls the hook once for each mapped service with a validated file path. It is accepted only for `install`. Production never invokes the hook implicitly: it requires an explicit map, and the lifecycle sets `skip_test_data=true` so production demo import cannot also enable test fixtures. The single-service `--demo_data` option is a compatibility form of the same mapping.

If a data-loading operation is reusable by every application using a framework, implement it in that profile instead of duplicating it in application hooks.

## Host bind-mount permissions

A bind mount maps a real host file or directory into a container. `set_application_host_bind_permissions` handles extra application-owned host paths before Compose validation and startup. Profile and addon paths already have their own generated callbacks.

Use the shared helper:

```bash
apply_host_permission_spec \
    "/srv/example/uploads|1000:1000|0775"
```

Each argument is `path|owner|mode`. Use `-` to leave ownership or mode unchanged. Missing paths are skipped, so create a required directory first. Use exact, validated paths only. Never target the host root or a broad parent, and do not use world-writable modes such as `0777`.

This hook changes an existing bind source; it does not add a mount to Compose. The mount must already be declared through the appropriate descriptor, profile/addon template, or supported application-owned topology.

## Running-container mount permissions

`set_application_running_mount_permissions` is called after generated profile/addon permission handling. Its signature is:

```text
$1  service name
$2  running container ID
```

Use it for an application-specific writable path as seen inside that container:

```text
host hook                         running-container hook
/srv/example/uploads             /opt/example/uploads
bind source on the host          mounted path inside the container
```

Named volumes may not have a normal host path that application code should manipulate. The shared in-container helper creates declared directories and applies ownership and mode recursively:

```bash
apply_container_directory_permission_spec "$container_id" \
    "/opt/example/uploads|1000:1000|u+rwX,g+rwX,o-rwx"
```

Dispatch on `service_name` so the hook never changes the wrong container. Use only paths already declared as writable storage by the deployment topology.

## Example: one extra writable directory

This illustrative block assumes the application service is named `example-app`, `HOST_UPLOAD_PATH` is an application installation setting, and the corresponding bind mount is already declared by a supported topology extension:

```bash
set_application_host_bind_permissions() {
    local upload_path uid gid
    upload_path="$(service_environment_value example-app HOST_UPLOAD_PATH)"
    uid="$(service_uid example-app)"
    gid="$(service_gid example-app)"

    mkdir -p "$upload_path"
    apply_host_permission_spec "$upload_path|$uid:$gid|0775"
}

set_application_running_mount_permissions() {
    local service_name="$1"
    local container_id="$2"
    local install_path uid gid

    [ "$service_name" = example-app ] || return 0
    install_path="$(service_install_path "$service_name")"
    uid="$(service_uid "$service_name")"
    gid="$(service_gid "$service_name")"

    apply_container_directory_permission_spec "$container_id" \
        "$install_path/uploads|$uid:$gid|u+rwX,g+rwX,o-rwx"
}
```

The setting belongs in both test and production installation-settings schemas. The mount declaration belongs with the topology owner. Only the two application-specific permission operations belong in this block.

## What not to customize here

Do not edit generated code to change the following:

- CLI parsing or lifecycle order;
- Docker/Podman selection and Compose invocation;
- configuration validation or Compose environment generation;
- generated service arrays, profiles, build contexts, or image names;
- readiness paths and waits;
- production build or profile bootstrap callbacks;
- profile/addon permission cases;
- generic permission helpers;
- smoke-test dispatch.

Choose the owner instead:

| Change needed | Correct owner |
|---|---|
| Different deployment value or path | `conf/*settings.txt` |
| Services, build contexts, database topology, or addons | Project descriptor |
| Django behavior | Django profile |
| Next.js or React/Vite behavior | Corresponding profile |
| Apache or Keycloak behavior | Corresponding addon |
| Reusable engine or permission behavior | Canonical `lib/container/` |
| Extra application-only writable path | Application deployment hook |
| Exact CLI and lifecycle contract | Container installer reference |

Never edit copies under `deployment/lib/` in an application repository. Reusable behavior belongs in the canonical `lib/container/` and is checked or synchronized with `scaffold.py check-lib` and `scaffold.py sync-lib`. See the [scaffold workflow](scaffold-workflow.md).

## Choosing the correct extension point

```text
Is it only a deployment value?
    -> installation settings

Does it change services or topology?
    -> project descriptor or the owning Compose profile/addon

Is it framework-specific?
    -> profile

Is it an optional infrastructure component?
    -> addon

Could every application reuse it?
    -> shared library or common template

Is it truly unique to this application?
    -> application-owned deployment hook
```

Do not create application hook logic merely because the hook is convenient.

## Docker, rootless Podman, and SELinux

Docker and Podman are supported. Docker is not required to run rootless. Rootless Podman maps container identities through a user namespace, so a container UID/GID may have different host IDs.

Application hooks should use `apply_host_permission_spec`, `apply_container_directory_permission_spec`, and the shared helpers they call. Those helpers use the implemented Podman `unshare` fallback or the scoped Docker helper-container fallback when an ordinary host operation fails. Avoid application-owned engine branches and direct broad `chown -R` commands.

Correct Unix ownership and mode do not guarantee bind-mount access when SELinux is enforcing. Compose profile/addon templates own their standard relabel options. An application-specific mount must follow that established labeling model; disabling SELinux is not the normal solution. See the [security requirements](../standards/security-requirements.md) and Podman [rootless-mode documentation](https://docs.podman.io/en/stable/markdown/podman.1.html#rootless-mode).

## Testing a customization

Start with static and scaffold checks:

```bash
bash -n container_install.sh

python3 /path/to/buisciii-deployment-standards/scripts/scaffold.py \
  check /path/to/application
```

Then exercise the real test lifecycle with an available engine:

```bash
bash container_install.sh \
  --test \
  --action install \
  --engine docker
```

Use `--engine podman` for the supported Podman path. Exercise permission hooks without rebuilding or bootstrapping by running:

```bash
bash container_install.sh \
  --test \
  --action fix-permissions \
  --engine docker
```

Confirm the generated Compose validation, readiness, smoke test, application behavior, and the exact ownership/mode of every added path. Configuration belongs in [Configuration](configuration.md), while mounts and topology belong in [Docker Compose](docker-compose.md).
