# MySQL Profile

Use this profile when an application owns or depends on MySQL.

## Required considerations

- Documentation MUST state whether MySQL is orchestrator-managed or external.
- Production databases SHOULD not publish a host port unless operationally
  required and protected.
- Application users MUST use least-privilege credentials; root credentials are
  for administration only.
- Character set and collation requirements MUST be explicit.
- The installer MUST wait for database readiness before initialization or
  migrations.
- Schema creation, migration, seed data, and production data imports MUST be
  separate operations.
- Production upgrades MUST NOT reload fixtures or destructive sample data by
  default.
- Backup and restore commands MUST cover the relevant schemas and be tested.
- Supported MySQL versions and upgrade constraints MUST be recorded.

