# Compose add-on catalog

Add-ons contribute marked blocks to the one generated Compose file and append
their services to `permission_services` when they own writable mounts. They do
not select or replace an application's framework profile.

The generator currently implements Apache and Keycloak directly in its Compose
assembler. The catalog directories document the configuration and permission
contract contributed by each add-on.
