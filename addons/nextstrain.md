# Nextstrain addon

## Addon overview

The Nextstrain addon is optional supporting infrastructure selected through `ADDONS.nextstrain`. It builds and runs an Auspice visualization service with `auspice view`, serving reviewed dataset and narrative files from deployment storage. It does not run a Nextstrain analysis pipeline, generate genomic datasets, or download data automatically.

Before starting a deployment, confirm that the deployment standards are synchronized to the expected commit or version. If they are not, follow the standards synchronization guideline, commit the synchronization changes, and then return to the deployment. Run the generated configuration check before starting containers.

## Generated service and files

| Path or service | Purpose | Ownership |
|---|---|---|
| `APP_SLUG-nextstrain` | Health-checked Auspice web service | Standard-managed Compose output |
| `nextstrain/Dockerfile` | Builds from `docker.io/nextstrain/base:latest` | Standard-managed generated file |
| `nextstrain/auspice-config.json` | Auspice build customization with a required JSON property schema | Application values and extra properties within a standard-managed schema |
| `conf/nextstrain/nextstrain_{test,production}_settings.txt` | Image, build, port, data-path, and public map settings | Standard-managed templates; production values are copied to protected settings |
| `nextstrain_data` | Dataset and narrative storage mounted at `NEXTSTRAIN_DATA_DIR` | Deployment/application data owner |

The Dockerfile copies `auspice-config.json`, substitutes the configured Mapbox token and style, and runs `auspice build --extend`. The resulting image starts `auspice view --customBuildOnly` with both its dataset and narrative directories set to `/data` by default.

## Auspice configuration

`nextstrain/auspice-config.json` starts with the required properties `browserTitle`, `mapTiles.api`, `mapTiles.attribution`, and `mapTiles.mapboxWordmark`. Its placeholder values are replaced at image build time using `MAPBOX_ACCESS_TOKEN`, `MAPBOX_STYLE_OWNER`, and `MAPBOX_STYLE_ID`.

The file is schema-preserving rather than fully overwritten. `scripts/scaffold.py check` accepts changed scalar values and additional local properties, reports missing standard properties as an available update, and rejects invalid JSON, duplicate object properties, or a scalar where the standard requires an object. `scripts/scaffold.py sync` recursively adds only missing standard properties while preserving local values and additional properties.

Edit application-specific Auspice values and extensions in this file, then run the scaffold check. Do not replace its object structure with an incompatible shape or rely on duplicate keys, because synchronization treats those cases as contract drift.

## Dataset ownership

The addon expects Auspice-compatible dataset JSON and narrative content at `/data` in the container. `NEXTSTRAIN_DATA_DIR` controls the volume mount destination and defaults to that path; it must remain `/data` with the current fixed `auspice view --datasetDir=/data --narrativeDir=/data` command. The application, analysis pipeline, or designated data owner produces and reviews those files; the addon only stores and serves them.

The repository does not prescribe the upstream analysis pipeline or dataset naming scheme. Dataset compatibility and scientific content remain outside the deployment addon.

## Data and update workflow

```text
application or analysis pipeline
    -> reviewed Auspice datasets and narratives
    -> copy through the running service into nextstrain_data
    -> auspice view
    -> browser visualization
```

Generated operations documentation uses Compose `cp` to copy reviewed host data through the running `APP_SLUG-nextstrain` service into the mounted volume. Copying updates matching paths but does not remove stale datasets, so obsolete files must be removed deliberately after a backup. A normal application upgrade preserves the named volume.

After an update, list the files through the running container and verify every expected dataset or narrative in the browser. The installer does not watch an external directory or automatically refresh the volume from pipeline output.

## Configuration ownership

The addon owns independent test and production settings under `conf/nextstrain/`. Settings select the local image name, build context and Dockerfile, internal and loopback host ports, mounted data directory, and public Mapbox build values. See the [configuration variable reference](../reference/configuration-variables.md) and [project descriptor reference](../reference/project-descriptor.md).

`ADDONS.nextstrain.CONFIG_SERVICE` is the common addon relationship field and defaults to the first application service, but it does not select a dataset, create an application route, or make the application generate data. `MODES` controls whether the service appears in production, test, or both. The generic `MOUNTS` option has no Nextstrain application-mount template and therefore does not add dataset mounts; the implemented dataset store is `nextstrain_data`.

The active templates use `MAPBOX_ACCESS_TOKEN`, `MAPBOX_STYLE_OWNER`, and `MAPBOX_STYLE_ID`. The access token is embedded in browser assets and is public rather than a server secret, but production still rejects the unresolved `CHANGE_ME` placeholder.

## Ports and networking

Auspice listens on `NEXTSTRAIN_PORT`, default `8100`, on all interfaces inside the container. Compose publishes it only on host loopback as `127.0.0.1:${NEXTSTRAIN_HOST_PORT}:${NEXTSTRAIN_PORT}` in both modes and connects the service to `deployment_net`.

When Apache is also selected, the generic addon dependency contract makes Apache wait for the Nextstrain service to become healthy. It does not generate an Apache virtual host or path route. Public access through Apache requires an application-owned route to the `APP_SLUG-nextstrain` Compose service and its internal port. Direct host diagnostics use the loopback URL; browser users need the public URL supplied by the surrounding infrastructure.

## Persistence and mounts

Both production and test mount the `nextstrain_data` named volume at `NEXTSTRAIN_DATA_DIR`; the default and currently required serving path is `/data`. A named volume survives container and image recreation until an operator explicitly removes it, so it is persistent deployment data in both generated modes rather than a read-only source bind.

The volume is writable because the documented update workflow copies datasets through the running service. The addon also mounts host timezone data read-only. It does not generate a host dataset bind or mount datasets read-only.

Generated operational documentation backs up the volume by streaming a `tar` archive through the running service. Dataset files and narratives must be included in the deployment's backup and restore plan; rebuilding the Auspice image does not recreate them.

## Permissions

The addon declares its service as a build target but has no addon-specific host-bind or running-volume permission callback. The container engine manages the named volume, and the repository does not impose a documented dataset UID/GID or chmod policy.

Operators should copy data through the running service instead of assuming an engine-specific host path for the volume. Rootless Podman may map container identities through a user namespace, while Docker manages its volume through its own engine path; neither storage path is a repository interface.

## Health and smoke checks

The Compose healthcheck performs an HTTP request to `/` on the configured internal port using Python inside the container. It verifies that Auspice returns an HTTP response, but it does not prove that a particular dataset or narrative exists, that a public proxy route works, or that the visualization content is scientifically correct.

The generated smoke script currently has no Nextstrain-specific endpoint or dataset assertion. Generated post-install guidance requires manual verification of the public route and every expected dataset or narrative before accepting the deployment.

## Test and production

The service topology, loopback port binding, writable `nextstrain_data` volume, image build, command, and HTTP healthcheck are the same in both modes. Test permits the obvious placeholder Mapbox token, while production requires `MAPBOX_ACCESS_TOKEN` and rejects unresolved production placeholders. `MODES` can omit the addon from either Compose document when explicitly configured.

Test and production use the same named volume name in their separate Compose models. Operators must account for the Compose project identity and selected environment when deciding whether those commands address isolated or shared engine resources.

## Customization and synchronization

| Content | Contract and correct owner |
|---|---|
| Generic image, Compose, settings, and documentation behavior | `scaffold/templates/addons/nextstrain/` |
| Required Auspice JSON property structure | Standard-managed schema |
| Auspice scalar values and additional configuration properties | Application-maintained `nextstrain/auspice-config.json` |
| Mapbox token and style used for a deployment build | Protected Nextstrain installation settings |
| Dataset and narrative contents | Application, analysis pipeline, or data owner; stored in `nextstrain_data` |
| Dataset generation and scientific analysis | External application/pipeline, not this addon |
| Generated Compose and settings templates | Do not edit directly; change supported inputs or upstream templates |

Run `scripts/scaffold.py check` before deployment and use `sync` to add missing standard JSON properties without replacing local values. Review synchronization changes before committing them.

## Security and operational notes

The host port is loopback-only, but public exposure can still be added by Apache or external infrastructure. The addon does not make an authorization or data-suitability decision for published datasets. The data owner must decide what may be served and through which public route.

The Mapbox access token becomes browser-visible build output and must be scoped as a public token. The named volume is writable operational data and should be backed up before replacing or removing datasets. DNS, external TLS, firewall policy, monitoring, and public-route access controls remain infrastructure responsibilities.

## Further reading

- [Auspice customization](https://docs.nextstrain.org/projects/auspice/en/stable/customise-client/)
- [Auspice narratives](https://docs.nextstrain.org/projects/auspice/en/stable/advanced-functionality/viewing-narratives.html)
