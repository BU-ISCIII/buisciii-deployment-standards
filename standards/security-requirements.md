# Security requirements

## 1. Purpose

This standard defines the security controls implemented or explicitly required by the BU-ISCIII deployment standard. It applies to generated container deployments and their shared installer behavior.

It is not a general hardening guide. Framework, identity-provider, and reverse- proxy requirements belong to their profiles or addons. Host access, firewall, TLS ownership, monitoring, and backup responsibilities are defined in [infrastructure requirements](infrastructure-requirements.md).

## 2. Security model

The deployment separates source and image build, runtime configuration, container startup, application bootstrap, persistent data, and verification.
This limits which phase receives sensitive values and prevents repeatable container startup from performing database installation work.

The common controls are summarized below.

| Area                     | Requirement                                                      | Reason                                               |
| ------------------------ | ---------------------------------------------------------------- | ---------------------------------------------------- |
| Runtime identity         | Application profiles run as their declared non-root user         | Limit privileges inside the container                |
| Production configuration | Real secrets stay out of committed templates                     | Avoid disclosure through source control              |
| Django production image  | Runtime settings are not rendered into the image                 | Avoid storing secrets in image layers                |
| Permissions              | Only declared paths are modified                                 | Avoid unintended host or container changes           |
| Rootless Podman          | User-namespace ownership is handled by Podman-specific fallbacks | Keep host and container ownership consistent         |
| Compose                  | The resolved model is validated before build or startup          | Reject invalid deployment input early                |
| Production data loading  | Demo data is never loaded implicitly                             | Prevent test data from entering production unnoticed |

Controls that are not implemented here, such as image signing, vulnerability
scanning, software bills of materials, and provenance attestation, are outside
the current contract.

## 3. Container privileges and engines

The Django profile runs with its configured application UID and GID. The Next.js profile runs as the image's `node` user, and the React/Vite profile runs as the unprivileged Nginx identity. These profile images MUST retain their non-root runtime user because their generated files, mounts, and permission preparation assume that identity.

Addon images may use a different vendor-defined user model. Their security requirements belong to the addon templates and documentation.

Docker and Podman are both supported. Docker is not required to run rootless.
Docker permission fallbacks use a short-lived, scoped helper container when a normal host operation is insufficient.

Rootless Podman creates a user namespace, which may map a container UID or GID to a different host ID. The shared permission helpers use `podman unshare` fallbacks where implemented. Podman-specific mapping behavior MUST NOT be presented as Docker behavior.

The selected engine and rootless-host requirements are defined in
[infrastructure requirements](infrastructure-requirements.md). Detailed command behavior belongs in the [container installer reference](../reference/scripts/container-install.md).

## 4. Filesystem permissions and SELinux

Permission operations MUST be limited to paths declared by profiles, addons, or the application-owned extension hooks. Permission helpers reject invalid or overly broad targets, including the host root.

Host bind sources and paths inside a running container are separate concerns.
The installer prepares host sources before startup and repairs writable container mounts after readiness. A mounted settings file uses a file-specific operation rather than recursive directory handling.

Deployments MUST NOT use broad world-writable modes such as recursive
`chmod 777` as a substitute for correct ownership. Exact UID, GID, and mode values remain profile- or addon-specific.

`fix-permissions` is an explicit repair operation. It MUST NOT build images, bootstrap applications, migrate databases, or load data.

SELinux applies access controls in addition to Unix ownership and modes. The generated Compose fragments use SELinux relabel options on applicable bind mounts and volumes. Where host policy or paths require further preparation, the operator MUST document and perform it outside the shared permission algorithm.
SELinux MUST NOT be disabled as the normal solution to a mount-access problem.

See the [container-install customization guide](../guides/container-install-customization.md) for application-owned permission and SELinux work.

## 5. Configuration and secrets

Committed production settings files are templates and MUST NOT contain real secrets. Operators MUST use protected, non-committed production copies. The outer installer rejects active production assignments containing `CHANGE_ME` before selecting the engine, building images, or starting services.

The installer writes the resolved Compose environment to a file with mode `0600`. This file may contain runtime secrets and MUST remain outside source control. It is not a Docker or Compose secret object.

Django production builds receive the selected settings source through the engine's build-secret interface. The Dockerfile consumes it with
`RUN --mount=type=secret`, while settings rendering remains disabled during production image staging. Production settings are rendered on the host instead, so Django secrets are not stored in an image layer.

For Django bootstrap, the installer copies configuration to a fixed temporary path inside the running container, assigns it to the application identity, and sets mode `0600`. The production copy is removed after the bootstrap attempt. Applications MUST NOT depend on that temporary file as persistent configuration.

Test settings contain disposable values and are allowed in the test image.
Their handling MUST NOT be described as the production secret model. See the [configuration guide](../guides/configuration.md) and [configuration variable reference](../reference/configuration-variables.md).

## 6. Image build and build context

Where a profile separates image staging from runtime bootstrap, image staging MUST NOT perform database migrations or load fixtures. Runtime bootstrap occurs only after the service is started and ready.

Production secrets MUST NOT be copied into image layers. Removing a sensitive file in a later Dockerfile instruction is insufficient because earlier layers remain part of the image.

The generated `.dockerignore` excludes production settings, generated runtime configuration, local environments, dependency trees, logs, persistent application data, and other non-build inputs. Only explicitly named non-sensitive test or template files are re-included. Generated deployments MUST preserve these exclusions or provide equivalent protection.

The generated `.gitignore` excludes local deployment configuration, generated synchronization candidates, runtime artifacts, dependency trees, logs, and document storage. It reduces accidental commits but does not replace review of staged changes.

Detailed patterns and maintenance guidance belong in the [ignore-files guide](../guides/ignore-files.md).

## 7. Network exposure

Compose provides an internal network for communication between selected services. Internal service names and ports SHOULD be used for communication inside that network rather than publishing support services unnecessarily.

The Django, Next.js, React/Vite, Keycloak, and Nextstrain templates bind their host-published application ports to loopback. This makes them available to a host proxy or local operator without exposing them on every host interface.

A selected Apache addon may be the public entry point and has an explicit bind- host setting. Its exposure and proxy policy belong to the [Apache addon documentation](../addons/apache.md). Databases and other support services MUST NOT be published publicly unless their selected template and documented topology explicitly require it.

Host firewall and external network rules belong in
[infrastructure requirements](infrastructure-requirements.md).

## 8. Test and production separation

Test and production use separate Compose files and configuration sources. Test configuration may contain disposable credentials, permissive application settings, local URLs, and disposable volumes. Those values MUST NOT be treated as production defaults.

Production configuration MUST NOT silently fall back to test configuration.
Generated production placeholders MUST be resolved before deployment. Test and production settings, environment files, Compose files, and persistent resources MUST remain distinguishable.

Test installations MAY load application-provided disposable data when that capability is implemented. Production MUST NOT load demo data implicitly. An explicit production demo import is accepted only for a fresh install with an existing file, and test fixtures remain disabled for that operation.

## 9. Persistent data

Persistent data and writable paths MUST be declared by the selected profile, addon, or application extension. Data that must survive container recreation MUST use a declared named volume, host bind, or external service rather than a replaceable container layer.

Permission preparation MUST use the declared host and in-container paths.
Install and upgrade recreate containers while preserving declared volumes and bind-mounted data. Operators MUST NOT infer persistence for an undeclared container path.

Backup ownership and recovery requirements are external to the installer and are defined in [infrastructure requirements](infrastructure-requirements.md) and the [backup and restore guide](../guides/backups-and-restore.md).

## 10. Validation and failure behavior

The installer MUST fail clearly for unsupported engines, actions, options, service mappings, missing files, invalid paths, and unresolved production placeholders where those inputs are handled by the common interface.

The resolved Compose model MUST validate before image build or service startup.
A deployment MUST NOT be accepted until required services pass readiness, profile bootstrap succeeds where applicable, and the generated smoke test passes.

Readiness confirms that a service can proceed to later lifecycle steps. The smoke test checks the deployed Compose model, service state, profile checks, and application health endpoints. Neither check is a substitute for continuous monitoring or application-specific security testing.

## 11. Profile and addon security

Common deployment code MUST remain independent of framework-specific security settings.

The following controls belong to their owners:

- Django `DEBUG`, secret key, allowed hosts, CSRF, CORS, email, and API   settings: [Django profile](../profiles/django.md);
- browser-visible build settings and server-side authentication configuration:
  [Next.js profile](../profiles/nextjs.md) or
  [React/Vite profile](../profiles/react-vite.md);
- identity bootstrap, realm data, credentials, and application OIDC settings:
  [Keycloak addon](../addons/keycloak.md); and
- public proxy, forwarded headers, request limits, status access, and TLS   integration: [Apache addon](../addons/apache.md).

Profile and addon requirements apply only when that component is selected.
Application-specific controls belong in application-owned configuration and extension hooks.

## 12. Worked example

The following example traces the implemented controls through one production Django deployment. It is illustrative and does not introduce new requirements.

1. An operator copies the generated production settings template to
   `deployment/settings/iskylims_production_settings.txt`, replaces all    placeholders, restricts the file to mode `0600`, and keeps it outside Git.
2. The installer rejects missing files and remaining active `CHANGE_ME` assignments before image build or service startup.
3. The production image build receives the settings source through
   `--secret`. Django staging does not render those settings into the image.
   4. The installer renders the protected host-side Django settings and writes the Compose environment file with mode `0600`.
5. Compose starts the Django container as its configured non-root UID/GID. Its published application port binds to `127.0.0.1`, while selected services communicate over the internal Compose network.
6. With rootless Podman, permission fallbacks use the deployment account's user namespace for declared paths. Docker follows its separate helper-container path and is not required to be rootless.
7. After readiness, the installer copies a temporary mode-`0600` configuration into the container, runs Django bootstrap, and removes the production copy after the attempt.
8. The generated smoke test must pass before the deployment is accepted. A host proxy or institutional TLS endpoint may then expose the application according to the documented infrastructure design.

If a declared volume later has incorrect ownership, the operator runs
`fix-permissions`. That operation repairs only declared paths; it does not rebuild the image or rerun migrations.

## 13. Further reading

External documentation explains the underlying technology but does not add requirements to this standard:

- [Docker build context and `.dockerignore`](https://docs.docker.com/build/concepts/context/)
- [Podman rootless mode](https://docs.podman.io/en/stable/markdown/podman.1.html#rootless-mode)
- [`podman unshare`](https://docs.podman.io/en/latest/markdown/podman-unshare.1.html)
