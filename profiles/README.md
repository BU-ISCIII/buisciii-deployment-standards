# Technology profiles

A profile describes framework- or application-specific deployment behavior. It complements, and does not replace, the common [application installation contract](../standards/application-installation-contract.md). Canonical generated artifacts live under [`scaffold/templates/profiles/`](../scaffold/templates/profiles/).

> **Status:** Existing profile requirements are retained; their detailed documentation will be expanded incrementally.

## Available profile documentation

- [Django](django.md)
- [Next.js](nextjs.md)
- [React and Vite](react-vite.md)

## Common future structure

1. Purpose / when to use the profile
2. Generated files
3. Build architecture
4. Runtime architecture
5. Profile-specific installer behavior
6. Dockerfile behavior
7. Compose behavior
8. Configuration
9. Persistent data
10. Permissions
11. Rootless container considerations
12. SELinux considerations
13. Deployment lifecycle
14. Upgrade lifecycle
15. Smoke tests
16. Security controls
17. Common failures
