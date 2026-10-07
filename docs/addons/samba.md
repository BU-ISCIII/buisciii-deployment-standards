# Samba addon

## Addon overview

The Samba addon provides disposable test/demo files to authenticated SMB clients on the deployment's internal Compose network. It creates one read-only SMB share backed by a writable test named volume. It is not generated as a production file service.

Before starting a deployment, confirm that the deployment standards are synchronized to the expected commit or version. If they are not, follow the standards synchronization guideline, commit the synchronization changes, and then return to the deployment. Run the generated configuration check before starting containers.

## Generated service and files

| Path or service | Purpose | Ownership |
|---|---|---|
| `APP_SLUG-samba` | Test-only SMB service using `docker.io/dperson/samba:latest` | Standard-managed test Compose output |
| `conf/samba/samba_test_settings.txt` | Disposable username and password | Standard-managed template with application/deployment test values |
| `conf/samba/samba_production_settings.txt` | States that Samba demo storage is unavailable in production | Standard-managed generated file |
| `samba_test_data` | Disposable test/demo file storage | Compose-managed named volume |

No custom image, Samba configuration file, host bind, or production service is generated.

## Shared paths

The named volume is mounted read-write at `/mnt` inside the Samba container. The configured share is named `ngs_data` and maps to `/mnt/test_ngs_data`.

SMB access to `ngs_data` is configured as browsable, authenticated, and read-only. The underlying named volume remains writable so application-owned `load_test_deployment_data` logic can populate fixtures or demo files before clients read them. The addon does not mount an application's production data volume or an operator-selected host directory.

## Configuration

`SAMBA_USER` and `SAMBA_PASSWORD` are the only Samba runtime settings. They are required by the test Compose command and are documented in the [configuration variable reference](../reference/configuration-variables.md). The generated test values are disposable defaults and are not production credentials.

The addon supports the common descriptor fields described in the [project descriptor reference](../reference/project-descriptor.md). `MODES` can suppress the test service when `test` is omitted, but selecting production cannot create a production Samba service because the production fragments intentionally contain only comments. `CONFIG_SERVICE` is normalized as addon context but does not change the share, credentials, or storage. `MOUNTS` has no Samba application-mount template and does not add shares.

## Users and authentication

The container command creates one Samba user from `SAMBA_USER` and `SAMBA_PASSWORD` and restricts the `ngs_data` share to that user. Guest access is disabled. Credentials come directly from test installation settings; they are neither generated randomly nor obtained from LDAP, Active Directory, or another external identity provider.

The repository implements no multi-user, group, domain, or credential-rotation model for this addon.

## Networking and ports

The service joins `deployment_net` and publishes no SMB port to the host. It is therefore reachable only by other containers on that Compose network unless a deployment changes the generated topology outside this addon contract.

The template does not publish TCP 445, TCP 139, or NetBIOS ports. It is not an externally exposed institutional share, and the repository provides no firewall or remote-client configuration for it.

## Permissions and ownership

The repository defines no Samba-specific host permission specification, container UID/GID, or running-volume ownership repair. The container image and engine manage the `samba_test_data` named volume, while the image command includes its own share-permission handling.

With rootless Podman, container identities may be translated through a user namespace, but this addon does not expose or manipulate the engine's host volume path. Docker follows its own named-volume behavior. Application hooks should populate data through declared container/Compose interfaces rather than changing an inferred host storage directory.

## SELinux

The volume mount uses `:z`, requesting a shared SELinux label suitable for container access where the engine supports relabeling. Unix ownership and SELinux labels remain separate controls. The addon does not disable SELinux or define extra host labeling commands.

## Persistence

`samba_test_data` survives ordinary container recreation until the Compose volume is explicitly removed, but the repository classifies it as disposable test/demo storage rather than production state. It has no generated production backup or restore workflow.

Production application storage remains external or application-declared and must have its own ownership, access, and recovery procedure. See the [backup and restore guide](../guides/backups-and-restore.md).

## Test and production

| Behavior | Test | Production |
|---|---|---|
| Samba service | Generated | Not generated |
| Storage | `samba_test_data` named volume | None |
| Share | Authenticated, browsable, read-only `ngs_data` | None |
| Credentials | Disposable `SAMBA_USER` and `SAMBA_PASSWORD` | No active settings |
| Host ports | None | None |

This addon is intentionally limited to test/demo use and is not a production-ready Samba deployment.

## Health and smoke checks

The Samba service has no Compose healthcheck. It uses `restart: unless-stopped`, but a running container does not prove that authentication or file access works.

The generated smoke script has no Samba-specific check. Generated post-install guidance requires a manual authenticated read/write workflow, but the current share is read-only to SMB clients; writes must occur through the fixture-loading or container-side data path. Operators should therefore verify authenticated listing and reading from an approved test client, plus the separate fixture-loading workflow when used.

## Security

The main implemented controls are test-only generation, disabled guest access, a single allowed user, read-only SMB access, no published host ports, and an SELinux-relabelled named volume. The default test password is intentionally disposable and must not be treated as a reusable secret.

The addon does not implement network segmentation beyond `deployment_net`, encrypted transport policy, domain integration, audit policy, or production credential management. Do not expose this test service to untrusted networks or use it for production data.

## Customization boundaries

| Change | Correct owner |
|---|---|
| Disposable test username and password | Samba test installation settings |
| Enable or suppress the test service | Project descriptor `ADDONS.samba.MODES` |
| Populate demo/fixture data | Application-owned `load_test_deployment_data` hook |
| Generic share, service, volume, and settings behavior | `scaffold/templates/addons/samba/` |
| Additional users, shares, write access, or published ports | Not supported by current addon inputs; requires an explicit generic addon change |
| Production file service, network policy, and recovery | Deployment/application infrastructure outside this addon |
| Generated Compose files | Do not edit directly |

## Further reading

- [Samba documentation](https://www.samba.org/samba/docs/)
