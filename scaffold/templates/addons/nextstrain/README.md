# Nextstrain add-on

The Nextstrain add-on runs `nextstrain view` as a health-checked visualization
service. It stores datasets in a named volume and exposes a loopback test port;
production access is normally provided by the selected reverse proxy add-on.

The add-on scaffolds a custom Auspice image build derived from the official
Nextstrain base image. Its build embeds the configured public Mapbox token and
style into `auspice-config.json`.
