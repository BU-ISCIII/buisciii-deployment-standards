- [`podman unshare`](https://docs.podman.io/en/latest/markdown/podman-unshare.1.html)
# Deployment standards

This directory contains normative requirements: statements about what must be true for a deployment to comply with the BU-ISCIII deployment standard.

Normative documents use **MUST** for requirements, **SHOULD** for recommendations that need a documented reason to omit, and **MAY** for optional behavior. Guides describe procedures, while reference pages describe the exact behavior or shape of an implementation artifact.

## Contents

- [Application installation contract](application-installation-contract.md)
- [Infrastructure requirements](infrastructure-requirements.md)
- [Security requirements](security-requirements.md)
- [Exceptions and compliance](exceptions-and-compliance.md)

## How to use these standards

1. Read the application installation contract for the common deployment model.
2. Confirm that the required host, access, network, TLS, monitoring, and backup arrangements satisfy the infrastructure requirements.
3. Review the cross-cutting security requirements.
4. Apply only the requirements for the profiles and addons selected by the project.
5. Assess the result and record intentional differences using the exceptions and compliance standard.

Worked examples explain how the requirements may fit together. Their hostnames, products, ports, paths, and resource sizes are illustrative and are not additional requirements.

Use the [installation checklist](../templates/installation-checklist.md) to collect evidence. Automated scaffold checks provide evidence about generated files and synchronization, but operational requirements still need review or execution evidence.
