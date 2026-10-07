# Nextstrain addon

This catalog entry builds a custom Auspice image from `docker.io/nextstrain/base:latest`, runs `auspice view`, and serves reviewed datasets and narratives from the writable `nextstrain_data` named volume. It does not generate or download datasets.

`nextstrain/auspice-config.json` is synchronized by required property schema: application scalar values and additional properties are preserved while missing standard properties can be added safely.

See the canonical [Nextstrain addon documentation](../../../../docs/addons/nextstrain.md) for data ownership, networking, persistence, and synchronization behavior.
