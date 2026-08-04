# Keycloak Profile

Use this profile when an application deploys or depends on Keycloak.

## Required considerations

- The realm configuration MUST have a declared source of truth.
- Public issuer URLs MUST exactly match the issuer expected by APIs.
- Browser redirect URIs and web origins MUST be exact HTTPS origins in
  production; localhost and wildcards MUST NOT be used.
- API audiences, browser client IDs, scopes, roles, and groups MUST be
  documented as a cross-service contract.
- Bootstrap and administrative credentials MUST not use test defaults in
  production.
- The Keycloak database MUST be persistent and included in backup and restore.
- Documentation MUST explain whether realm import applies only on first start
  and how an existing realm is upgraded.
- SMTP MUST be configured and tested when required actions send email.
- Reverse-proxy hostname and TLS settings MUST be documented.
- Keycloak and database upgrades MUST include compatibility and rollback steps.

## Suggested smoke test

Verify discovery metadata, login, token issuer and audience, API acceptance of a
valid token, API rejection of an invalid token, and the required role/group
authorization.

