# Exceptions and compliance

## 1. Purpose

This standard defines how a BU-ISCIII deployment is assessed for compliance and how intentional exceptions are recorded. It applies to developers, operators, and reviewers using the common standards, selected profiles, and selected addons.

## 2. Compliance model

A deployment has one of these compliance states:

### Compliant

All applicable `MUST` requirements are satisfied. Any difference from a `SHOULD` requirement has a documented reason.

### Compliant with documented exceptions

One or more applicable `MUST` requirements are intentionally not satisfied, and every difference has an explicit exception record containing the information required below and evidence that it was accepted through the application's review process.

### Non-compliant

One or more applicable `MUST` requirements are not satisfied and no accepted exception is documented. Missing evidence that prevents a requirement from being assessed is an unresolved deviation, not proof of compliance.

Audit reports MAY use more detailed finding terms such as `Meets`, `Partial`, or `Does not meet`. The final compliance state still follows the definitions above.

## 3. Applicable requirements

Normative words have these meanings:

- **MUST** is required for compliance unless an accepted exception applies.
- **SHOULD** is the expected approach. A deployment may differ when it records
a clear reason; that difference alone does not make the deployment non-compliant.
- **MAY** describes an optional choice.

Common requirements apply to every deployment within their stated scope. Profile requirements apply only to services selecting that profile. Addon requirements apply only when that addon is selected and enabled for the deployment mode.

A deployment mode that an application explicitly does not support does not become applicable merely because another application or template supports it. The unsupported mode itself MUST be documented where the standards require it.

Application-specific behavior is not automatically an exception. Using a marked application-owned block or extension hook for behavior expected to vary between applications is normal compliance. Application-specific requirements belong in the application repository.

The applicable common requirements are defined in:

- the [application installation contract](application-installation-contract.md);
- [infrastructure requirements](infrastructure-requirements.md); and
- [security requirements](security-requirements.md).

## 4. Exceptions

An exception MUST be explicit, narrow, and linked to an applicable requirement. It MUST NOT be used to hide an unknown status or missing evidence.

At minimum, an exception record MUST contain:

| Field         | Required content                                                                |
| ------------- | ------------------------------------------------------------------------------- |
| Requirement   | Section link or exact requirement text                                          |
| Scope         | Application, component, environment, and deployment mode affected               |
| Reason        | Why the requirement cannot or should not be followed                            |
| Constraint    | Technical or operational condition causing the difference                       |
| Impact        | Known risk or operational consequence                                           |
| Mitigation    | Alternative control or procedure, if any                                        |
| Owner         | Person or team responsible for the exception                                    |
| Review record | Date and evidence of acceptance under the application's existing review process |

Requirement IDs MUST NOT be invented when the source standard uses section links instead.

Example:

| Field         | Value                                                                                                       |
| ------------- | ----------------------------------------------------------------------------------------------------------- |
| Requirement   | [Infrastructure requirements: backups and recovery](infrastructure-requirements.md#10-backups-and-recovery) |
| Scope         | Example service, production                                                                                 |
| Reason        | The database is externally managed                                                                          |
| Constraint    | The application deployment account cannot run database backups                                              |
| Impact        | Recovery does not use the generated application procedure                                                   |
| Mitigation    | Institutional DBA backup and restore procedure                                                              |
| Owner         | Application team                                                                                            |
| Review record | Reviewed with the production deployment documentation                                                       |

An exception applies only to its recorded scope. It does not change the common standard or automatically apply to another service, environment, or application.

An exception is accepted only when its review record shows acceptance through the application's existing process. A proposed exception without that evidence remains an unresolved deviation.

## 5. Compliance evidence

A compliance assessment SHOULD link each finding to evidence. Depending on the requirement, evidence may include:

- scaffold-generated files and saved descriptor state;
- output from `scripts/scaffold.py check` or `check-lib`;
- syntax, scaffold, Compose, installation, upgrade, and smoke-test results;
- reviewed test and production configuration;
- the completed [installation checklist](../templates/installation-checklist.md);
- application `README.md` and production `LEAME.md`;
- infrastructure or operational records; and
- an application audit in [`audits/`](../audits/).

`scripts/scaffold.py check` reports generated-file updates, managed drift, contract drift, missing or obsolete artifacts, and shared-library drift. A successful result is evidence that the generated baseline is synchronized; it does not prove operational, infrastructure, or security compliance.

Automated checks cover only requirements they directly exercise. Requirements about ownership, external services, recovery, production access, or completed operations require manual review or execution evidence.

## 6. Audits and reviews

Files in [`audits/`](../audits/) assess a real application or implementation area against the standard. An audit may record satisfied requirements, partial implementation, deviations, missing evidence, and recommendations.

An audit describes the evidence available at the time it was performed. It does not automatically accept an exception, change an application, or modify the common standard.

The installation checklist is a review aid, not a replacement for the standards. A checked item SHOULD link to the file, command, test result, or operational record that supports it. Findings and intentional exceptions SHOULD be recorded in its findings table or in a linked application-owned document.

## 7. Worked assessment example

The following example shows how a reviewer can combine automated and manual evidence. It is illustrative and does not define an approval authority.

| Requirement                                                        | Applicable evidence                                      | Finding                            |
| ------------------------------------------------------------------ | -------------------------------------------------------- | ---------------------------------- |
| Generated files match the current scaffold                         | Successful `scripts/scaffold.py check` output            | Satisfied for synchronization only |
| Production configuration is protected and contains no placeholders | File-mode inspection and installer validation output     | Satisfied                          |
| Installation ends with a passing smoke test                        | Retained production-like installation log                | Satisfied                          |
| TLS ownership and renewal are documented                           | Infrastructure record naming the Forti/certificate owner | Satisfied by manual review         |
| Restore procedure has been exercised                               | No restore record is available                           | Unresolved deviation               |

Because the restore evidence is missing, the reviewer cannot mark the deployment compliant merely because scaffold and smoke checks pass. The team must either perform and record the restore exercise or document an exception if an applicable requirement will intentionally not be followed.

For example, suppose the application standard requires operational details in `LEAME.md`, but an application intentionally keeps the authoritative recovery procedure in a centrally controlled operator runbook. An exception record could identify the documentation requirement and application, explain the central runbook constraint, describe the risk that the repository copy is incomplete, link the controlled runbook as the mitigation, name its owner, and record its acceptance through the application's existing review process.

Using an application-owned deployment hook does not need such an exception when the hook is the extension point provided by the standard and all applicable requirements remain satisfied.

## 8. Resolving deviations

A reviewer MUST distinguish an intentional exception from an unresolved deviation. An unresolved deviation includes a failed requirement, missing evidence, unknown applicability, or proposed exception without recorded acceptance.

Resolve a deviation by choosing the appropriate outcome:

1. fix the application when it incorrectly diverges from an applicable requirement;
2. document and accept a narrow exception when the difference is intentional; or
3. update the common standard only when the behavior is reusable and should apply broadly.

The common standard MUST NOT be changed solely to make one application's special behavior appear compliant. Reusable behavior belongs in the common layer, a profile, or an addon; application-only behavior remains in the application repository.
