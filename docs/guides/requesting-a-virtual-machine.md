# Requesting a development virtual machine

This guide helps an application maintainer request a development VM or equivalent Linux host from IT. It collects the information IT needs without prescribing how IT configures the host internally.

The normative requirements are in [infrastructure requirements](../standards/infrastructure-requirements.md). Production needs are summarized separately at the end of this guide.

## 1. Decide what will run

Before requesting the VM, identify:

- the application and repository;
- the developers who will use the host;
- the application services and selected profiles;
- whether the development database runs in Compose or is external;
- selected addons such as Apache, Keycloak, Nextstrain, or Samba;
- test datasets or uploaded files that need storage;
- Docker or Podman as the container engine; and
- how developers will reach the application.

A development VM normally uses disposable test settings and test Compose services. Do not put production credentials or production data on it.

## 2. Estimate host resources

Estimate resources for everything that will run on the VM, including application containers, development databases, addons, image builds, and test data.

Separate the system disk used by Linux, container images, and build cache from persistent or large development datasets when that makes operations clearer. State the expected initial usage and growth.

For example only:

| Resource | Example request | Reason |
| --- | --: | --- |
| vCPU | 4 | Application containers and image builds |
| RAM | 8 GB | Application, development database, and addons |
| System disk | 40 GB | Linux, images, build cache, and logs |
| Data disk | 100 GB | Test datasets and uploaded development files |

These values are not standard minimums. Adjust them to the application and explain the estimate.

## 3. Choose the operating system

Request:

- a Linux distribution and version supported by IT;
- responsibility for operating-system updates;
- Bash and normal Linux filesystem and network tools;
- support for the selected container engine; and
- the expected SELinux state.

Do not ask IT to disable SELinux. The generated Compose files use relabel options where applicable, but institutional paths may still need documented preparation.

## 4. Request the development account and SSH access

State:

- the account name and owner;
- whether developers use named accounts or an approved shared service account;
- SSH public keys or automation identity;
- source networks allowed to connect;
- required repository and directory access; and
- any limited `sudo` task needed for initial host preparation.

Routine deployment commands should not need unrestricted administrative access.

For rootless Podman, the same account must run Podman, its Compose provider, and `container_install.sh`. Ask IT to configure subordinate UID/GID ranges, user namespaces, and a method for development services to continue after logout or reboot when needed.

## 5. Choose Docker or Podman

For Docker, request Docker Engine and the `docker compose` plugin. Docker does not have to be rootless, but the development account needs approved access to the daemon.

For Podman, request Podman and either `podman-compose` or a working `podman compose` provider. For rootless Podman, confirm that its storage filesystem and the account configuration support rootless containers.

If the Django profile will be built in production-like mode on this VM, the engine must support the `--secret` build option and Dockerfile `RUN --mount=type=secret` syntax.

## 6. Request development DNS and network access

Decide whether developers will use SSH port forwarding, a host-local URL, an internal development DNS name, or an institutional development proxy.

For example, the team may request `iskylims.isciiides.es` for internal development access over HTTP. DNS only maps the name to an address; the request must also say how traffic reaches the application.

Generated application ports normally bind to host loopback. Remote access therefore needs a documented path such as SSH forwarding, a reverse proxy on the VM, or an institutional proxy that can reach the backend port. Do not ask to expose a database publicly.

For every inbound rule, give the exact source network, destination host, protocol, port, and purpose. For example:

| Source | Destination | Protocol/port | Purpose |
| --- | --- | --- | --- |
| `<development-CIDR>` | `dcontainers00` | TCP 22 | Developer SSH access |
| `<development-proxy>` | `dcontainers00` | TCP `<backend-port>` | Internal HTTP access to iSkyLIMS |

### Exact outbound destinations

Do not request generic “internet access.” Give IT an allow-list containing the exact URL or FQDN, protocol, port, and reason for every external dependency. Derive the list from the selected profiles, addons, base images, package managers, repository remotes, and application integrations.

Use a table like this:

| URL or FQDN | Protocol/port | Purpose | Required by |
| --- | --- | --- | --- |
| `https://github.com/BU-ISCIII/relecov-iskylims.git` | HTTPS/TCP 443 | Clone and update application source | Deployment workflow |
| `registry.access.redhat.com` | HTTPS/TCP 443 | Pull the Django UBI base image | Django profile |
| `github.com/aptible/supercronic` | HTTPS/TCP 443 | Download the pinned Supercronic release | Django profile |
| `registry-1.docker.io` | HTTPS/TCP 443 | Pull images hosted on Docker Hub | Selected image references |
| `auth.docker.io` | HTTPS/TCP 443 | Docker Hub registry authentication | Docker Hub pulls |
| `https://pypi.org/simple/` | HTTPS/TCP 443 | Resolve Python packages | Django profile |
| `files.pythonhosted.org` | HTTPS/TCP 443 | Download Python package files | Django profile |
| `https://registry.npmjs.org/` | HTTPS/TCP 443 | Resolve and download Node packages | Next.js or React/Vite profile |
| `<exact-OS-mirror-FQDN>` | HTTPS/TCP 443 | Install operating-system packages | Selected Linux distribution |
| `<exact-SMTP-FQDN>` | TCP `<SMTP-port>` | Send development email | Application configuration |
| `<exact-identity-provider-URL>` | HTTPS/TCP 443 | Development authentication | Application or Keycloak integration |
| `<exact-external-API-URL>` | HTTPS/TCP 443 | Application integration | Application configuration |

Keep only the rows the deployment actually needs and replace every placeholder. If IT provides institutional Git, container-registry, PyPI, npm, or OS-package mirrors, request those exact mirror URLs instead of the public endpoints.

DNS and time synchronization may be supplied as infrastructure services rather than URLs. Record their exact server addresses when IT requires them in the allow-list.

TLS is normally a production concern for this request. If institutional policy also requires HTTPS on development hosts, record the TLS endpoint and owner explicitly.

## 7. Describe development storage and database access

List data that should survive container recreation, even if it is not a production backup requirement:

- development database volumes;
- uploaded files or test datasets;
- addon data;
- logs needed for debugging; and
- local protected settings.

State the exact path or volume name, initial size, expected growth, owner, and whether the data is disposable. The installer changes permissions only on declared paths, so include every host bind path the deployment will use.

For a database, first state whether it is created by the test Compose model or supplied externally.

### Compose development database

When the selected profile creates its own test database, record the Compose service name, database name, application user, named volume, and whether `down -v` may delete it. These values come from the application's test settings and do not require IT to create a separate database account.

### External development database

When IT or a DBA provides the database, include all of the following:

| Field | Information to provide |
| --- | --- |
| Database engine | For example, MySQL 8 |
| Server | Exact FQDN or IP address |
| Port | Exact database port |
| Database/schema name | Exact development database name |
| Application user | Exact username used by the application |
| Source | VM address or network allowed to connect |
| Grants | Exact privileges required on that database/schema |
| Owner | Team that creates credentials and manages the server |
| Storage | Initial capacity and expected growth |
| Lifecycle | Whether the database is disposable and who may reset it |

A Django service that runs migrations needs schema-change privileges in addition to normal reads and writes. For example, a dedicated MySQL development account might receive:

```sql
CREATE DATABASE iskylims_dev;
CREATE USER 'iskylims_dev_user'@'<development-vm-address>'
  IDENTIFIED BY '<generated-password>';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES
  ON iskylims_dev.*
  TO 'iskylims_dev_user'@'<development-vm-address>';
```

This is an example, not a universal grant list. Review the application's migrations and institutional database policy, grant access only to the named development database, and use the protected application settings to store the resulting connection values. Do not put the password in the VM request ticket unless that is the approved secret-delivery channel.

Production data and credentials must not be copied to the development VM unless an approved exception defines how they are protected.

## 8. Complete example request

The following example is part of this guide; no separate request template is required. Replace every example value before sending it to IT.

| Field | Example development request |
| --- | --- |
| Application | iSkyLIMS development environment |
| Repository | Application repository and branch used by the development team |
| Users | Named developers connecting from the institutional development network |
| Hostname | VM `dcontainers00` |
| Operating system | Rocky Linux 9, maintained by the infrastructure team, with SELinux enforcing |
| Resources | 4 vCPU, 8 GB RAM, 40 GB system disk, and 100 GB data disk |
| Account | `svc-iskylims-dev`, with approved SSH keys and access to declared deployment directories |
| Engine | Rootless Podman with a working Compose provider |
| Rootless setup | Subordinate UID/GID ranges, user namespaces, and persistence after logout configured |
| Services | Django application and selected test addons; database supplied externally |
| Development DNS | `iskylims.isciiides.es` |
| Application access | Internal HTTP through the documented development proxy or backend path |
| SSH | TCP 22 from the approved development administration network |
| Outbound access | Exact allow-list: `https://github.com/BU-ISCIII/relecov-iskylims.git`, `registry.access.redhat.com`, `https://github.com/aptible/supercronic/`, `registry-1.docker.io`, `auth.docker.io`, `https://pypi.org/simple/`, `files.pythonhosted.org`, and the approved Rocky Linux mirror; TCP 443 |
| Database | External MySQL at `db-dev.isciii.es:3306`; database `iskylims_dev`; user `iskylims_dev_user`; access allowed from `dcontainers00`; grants limited to `iskylims_dev.*` |
| Storage | 100 GB data disk for uploaded test files and logs; protected settings stored on the system disk |
| Data classification | Disposable test data only; no production credentials or production records |
| SELinux | Enforcing; declared bind paths supplied for any required labeling review |
| Owner | Application team owns the deployment; infrastructure team owns the VM and operating system |

A copyable request can be as short as:

```text
Please provide a development VM for iSkyLIMS.

Host: dcontainers00
OS: Rocky Linux 9 with SELinux enforcing
Resources: 4 vCPU, 8 GB RAM, 40 GB system disk, 100 GB data disk
Account: svc-iskylims-dev with SSH-key access from <source network>
Engine: rootless Podman with a Compose provider
Rootless setup: subordinate UID/GID ranges and persistence after logout
Development DNS: iskylims.isciiides.es
Application access: internal HTTP through <proxy or backend path>
Outbound HTTPS/TCP 443: https://github.com/BU-ISCIII/relecov-iskylims.git, registry.access.redhat.com, https://github.com/aptible/supercronic/, registry-1.docker.io, auth.docker.io, https://pypi.org/simple/, files.pythonhosted.org, <Rocky-mirror-FQDN>
Database: MySQL at db-dev.isciii.es:3306; database iskylims_dev; user iskylims_dev_user; source dcontainers00; grants SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP and REFERENCES on iskylims_dev.*
Storage: 100 GB for test uploads and logs; protected settings on system disk
Data: disposable development data only
Owners: <application owner> and <infrastructure owner>
```

## 9. Before using the VM

Confirm that:

- the assigned CPU, memory, and disks match the request;
- the selected Linux version and container engine are installed;
- SSH access works from the approved network;
- the development account can run the Compose provider;
- rootless Podman prerequisites work, when selected;
- required storage and bind paths exist;
- development DNS and the chosen access path work;
- required outbound destinations are reachable;
- SELinux handling is documented; and
- only development settings and data are present.

Run the generated test installation and smoke test before treating the environment as ready.

## 10. Potential production needs

A later production request needs decisions that are intentionally outside the development VM request:

- production capacity, availability, and storage growth;
- stable production DNS such as `iskylims.isciii.es`;
- HTTPS and TLS termination, for example an institutional Forti appliance presenting and renewing the certificate;
- the network path from the public TLS endpoint to the application or proxy;
- production deployment and operator accounts;
- external database, SMTP, identity, API, and storage ownership;
- protected production configuration and secrets;
- production logging, monitoring, alerts, and incident ownership;
- backup scope, retention, off-host storage, recovery objectives, and restore tests; and
- rollback and production acceptance evidence.

For example, `https://iskylims.isciii.es` means that the client uses TLS. If Forti terminates TLS, the production request must identify who owns the certificate, how it is renewed, and whether Forti forwards to a private HTTP or HTTPS backend.

Follow [Preparing production infrastructure](preparing-production-infrastructure.md) for the production procedure. It uses the full [infrastructure requirements](../standards/infrastructure-requirements.md), [security requirements](../standards/security-requirements.md), and generated production `LEAME.md`.
