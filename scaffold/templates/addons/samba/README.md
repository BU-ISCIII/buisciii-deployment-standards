# Samba test-data addon

This catalog entry creates an authenticated, read-only `ngs_data` SMB share backed by `samba_test_data` only in the test Compose model. It has no production service or published host ports.

Applications may populate disposable data through their preserved `load_test_deployment_data` hook. See the canonical [Samba addon documentation](../../../../docs/addons/samba.md) for the exact limitations.
