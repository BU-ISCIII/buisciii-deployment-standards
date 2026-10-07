# Preparing production infrastructure

This guide turns the [infrastructure requirements](../standards/infrastructure-requirements.md) into a production-readiness procedure. It helps application, infrastructure, security, and operations owners agree what must exist before deployment; it does not prescribe how an infrastructure provider implements hosts, networks, certificates, or backup systems.

## 1. Select the deployment scope

Record the application, environment, application revision, approved deployment-standards commit or version, project descriptor, application services, selected profiles, selected addons, and production database model. Use the [project descriptor reference](../reference/project-descriptor.md) to identify the generated topology and the profile and addon pages to identify component-specific requirements.

Do not start production installation until the application repository passes `scaffold.py check` against the selected standards revision with every item reported as `current`. If it does not, follow the [Scaffold workflow](scaffold-workflow.md), commit the synchronized files and scaffold state, and then return to this procedure.

## 2. Assign owners

Identify the owner of the application, host and operating system, deployment account, container engine, network and DNS, TLS endpoint and certificate renewal, external database and integrations, production configuration, logging and monitoring, backups and restore, deployment execution, acceptance, and rollback decision.

Record the approved exception for any applicable requirement that cannot be satisfied. An unresolved owner or unapproved exception means the infrastructure is not ready.

## 3. Confirm host capacity and storage

Document the Linux distribution and version, maintenance owner, support lifetime, CPU, memory, and storage. Capacity must cover application services, selected addons, image builds, concurrent deployment work, expected workload, growth, logs, and recovery material.

Inventory every named volume, host bind source, external database, protected configuration file, and log location. For each persistent resource, record its host or service location, capacity, expected growth, required performance, filesystem ownership, backup scope, and responsible owner. Keep backup capacity separate from live deployment capacity.

## 4. Prepare access and the container engine

Create or identify the deployment account and record its owner, SSH or approved remote-access method, authorized identities, source restrictions, groups, working directories, and limited administrative tasks. Confirm that the account can read the repositories and protected configuration, run the selected engine and Compose provider, and create or update only the declared deployment paths.

For Docker, record the Docker and Compose versions and confirm the approved daemon-access model. Docker is not required to run rootless. For Podman, record the Podman and Compose-provider versions. When Podman runs rootless, verify subordinate UID/GID mappings, user namespaces, `podman unshare`, compatible storage, and the mechanism that keeps services available after logout or reboot. Use the same account for the installer, Podman, and its Compose provider.

Confirm that the engine supports every build feature required by the selected profiles. Django production builds require build secrets and Dockerfile `RUN --mount=type=secret` support.

## 5. Prepare network, DNS, and TLS

Record every required inbound and outbound path with source, destination, protocol, port, purpose, and owner. Derive the list from the selected profiles, addons, image registries, source repositories, package sources, external databases, email, identity providers, APIs, monitoring, and backup services. Keep databases and internal Compose services private unless a documented integration requires access.

For each external hostname, record the DNS owner, resolution scope, target, and expected route to the generated deployment. For every externally exposed production HTTP service, record the TLS termination point, certificate names, issuer, installation owner, renewal process, expiry monitoring, and backend protocol. Ensure that the public scheme, host, port, forwarded values, application allowed hosts, and identity-provider URLs agree.

The generated deployment does not provision institutional DNS, firewall rules, certificates, external load balancers, or TLS terminators.

## 6. Prepare paths, permissions, and SELinux

List the host paths required by the generated production Compose model and protected configuration mappings. Record the expected owner, group, mode, and whether each mount is read-only or writable. Do not use broad recursive permissions as a substitute for declaring the required paths.

Record the host SELinux state. When SELinux is enforcing, confirm that generated relabel options and any required path-specific infrastructure preparation cover every bind mount. Document manual labels or policy exceptions in the production runbook; do not disable SELinux merely to make a mount work.

## 7. Prepare production configuration and integrations

Identify a protected, non-committed settings file for every configured application and addon. Record its owner and delivery location without copying secret values into the readiness record. Follow [Configuration](configuration.md) for settings ownership, component mappings, build-time values, runtime values, and validation.

Confirm the ownership and expected endpoints of external databases, email, identity, APIs, storage, proxies, and other application integrations. Infrastructure readiness confirms that the required paths and services are supplied; the deployment configuration check and application acceptance tests verify the values and behavior later.

## 8. Prepare operations and recovery

Record log sources, destinations, access controls, rotation, retention, monitored health endpoints, alert recipients, and response ownership. The generated smoke test runs during deployment but does not provide continuous monitoring.

Inventory all authoritative production data and follow [Backups and restore](backups-and-restore.md). Record backup method, schedule, retention, off-host location, access controls, recovery objectives, restore operator, and evidence from a restore test. Review [Upgrades and rollback](upgrades-and-rollback.md) and name the person authorized to choose rollback during the deployment window.

## 9. Record readiness and handoff

The production infrastructure record should contain:

| Area | Required record |
| --- | --- |
| Scope | Application revision, standards revision, descriptor, services, profiles, addons, and database model |
| Host | Linux version, maintenance owner, CPU, memory, storage, growth, and support lifetime |
| Access | Deployment account, authorized identities, source restrictions, privileges, and removal owner |
| Engine | Docker or Podman version, Compose provider, account model, and required build-feature support |
| Storage | Named volumes, bind sources, external data, configuration paths, logs, permissions, and owners |
| Network | Every inbound and outbound source, destination, protocol, port, purpose, and owner |
| DNS and TLS | Hostnames, DNS owner, route, termination point, certificates, renewal, monitoring, and backend protocol |
| Integrations | Database, email, identity, APIs, storage, proxies, endpoints, and owners |
| Security | Secret-delivery boundary, SELinux state, mount labeling, and approved exceptions |
| Operations | Logging, monitoring, alerts, backups, restore evidence, recovery objectives, and rollback owner |
| Approval | Application, infrastructure, security, and operations review evidence required by the local process |

Before handoff, verify that the host, account, engine, Compose provider, directories, network paths, DNS, TLS ownership, monitoring, backups, and restore responsibilities are ready. Record unresolved items as blocking findings or approved exceptions. Then continue with [Configuration](configuration.md) and the [Deployment workflow](deployment-workflow.md); infrastructure readiness alone does not prove that the application deployment is accepted.
