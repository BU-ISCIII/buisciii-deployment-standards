# Samba test-data add-on

This add-on creates a Samba service and named data volume only in the test
Compose profile. Applications may populate it from an application-owned
`deployment/hooks/test_data.sh` hook.
