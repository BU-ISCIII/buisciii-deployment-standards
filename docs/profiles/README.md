# Application profiles

A profile defines how an application service is built, started, and deployed. The scaffold currently accepts exactly these profiles:

- [Django](django.md) — Python/Django build, settings, Gunicorn runtime, migrations, and bootstrap.
- [Next.js](nextjs.md) — Node build/runtime, server configuration, readiness, and health behavior.
- [React/Vite](react-vite.md) — static frontend build served by Nginx.

Profiles complement the common [application installation contract](../standards/application-installation-contract.md). Their implementation sources remain under [`../../scaffold/templates/profiles/`](../../scaffold/templates/profiles/).
