# Django Profile

Use this profile for Django applications in addition to the core contract.

## Required considerations

- Production `SECRET_KEY` MUST be stable across restarts, kept secret, and not
  replaced during a normal upgrade.
- `DEBUG` MUST be disabled in production.
- `ALLOWED_HOSTS`, CSRF trusted origins, and CORS policy MUST be explicit.
- Database migrations MUST run in a controlled step and failure MUST stop the
  deployment.
- `collectstatic` ownership and persistence behavior MUST be documented.
- Creation of a default superuser MUST be disabled by default in production.
- Email configuration and failure behavior MUST be documented when application
  workflows depend on email.
- The WSGI/ASGI server, worker count, timeouts, and proxy headers MUST be
  configurable for production.
- Django system checks SHOULD be part of the smoke test.

## Suggested validation

```bash
python manage.py check --deploy
python manage.py showmigrations
```

Projects should add endpoint, authentication, and data checks appropriate to
their application.

