# Creating a project

This guide explains how to create the initial BU-ISCIII deployment baseline in a new or existing application repository.

## 1. Prerequisites

You need the application repository, a checkout of `buisciii-deployment-standards`, Python 3, and the application information required by the project descriptor. The standards repository does not need to be copied into the application repository.

If the development infrastructure is not ready, see [Requesting a virtual machine](requesting-a-virtual-machine.md).

## 2. Prepare the application repository

For an existing repository:

```bash
git clone <application-repository>
cd <application-repository>
```

For a new repository:

```bash
mkdir example-app
cd example-app
git init
```

The scaffold can write into an existing application repository. Review any existing files before initialization because generated paths may overlap with them.

## 3. Create the project descriptor

Copy the current example to a temporary file and edit it for the application:

```bash
cp /path/to/buisciii-deployment-standards/scaffold/project.json.example \
   /tmp/example-app.json
```

The descriptor defines the application identity and deployment topology used to select and render the scaffold templates. The following single-service Django descriptor uses the current schema:

```json
{
  "APP_NAME": "Example Application",
  "APP_SLUG": "example-app",
  "DESCRIPTION": "Example application",
  "REPOSITORY_URL": "https://github.com/BU-ISCIII/example-app.git",
  "DEFAULT_BRANCH": "main",
  "PYTHON_VERSION": "3.11",
  "TIMEZONE": "Europe/Madrid",
  "SERVICES": {
    "example-app": {
      "PROFILE": "django",
      "BUILD_CONTEXT": ".",
      "DOCKERFILE": "Dockerfile",
      "IMAGE": "example-app:local",
      "INSTALL_CONF": "conf/docker_production_settings.txt",
      "TEST_INSTALL_CONF": "conf/docker_test_settings.txt",
      "PROJECT_MODULE": "example_app"
    }
  },
  "ADDONS": {}
}
```

Use [Project descriptor](../reference/project-descriptor.md) for field definitions. The repository also provides [`scaffold/project.addons.json.example`](../../scaffold/project.addons.json.example) for a deployment with selected addons.

## 4. Choose services, profiles and addons

A **service** is a deployable application component. A standalone application normally defines one service, while an orchestrator may define several. Service names become stable deployment identities, so use meaningful names such as `iskylims-web` or `iskylims-api` instead of generic names such as `app` or `service1` when possible.

A **profile** supplies framework-specific deployment behavior. The scaffold currently supports `django`, `nextjs`, and `react-vite`.

An **addon** is an optional supporting deployment component. The scaffold currently supports `apache`, `keycloak`, `nextstrain`, and `samba`.

At most one service may use `BUILD_CONTEXT: "."` and own the profile artifacts in the current repository. Services assembled by an orchestrator normally use sibling or other external build contexts. See [Project descriptor](../reference/project-descriptor.md) for the complete service and addon rules.

## 5. Generate the baseline

Run `init` from any directory, giving it the application repository and descriptor paths:

```bash
python3 /path/to/buisciii-deployment-standards/scripts/scaffold.py \
  init /path/to/example-app \
  --config /tmp/example-app.json
```

`init` creates the baseline from the common templates, selected profile, and selected addons. Do not manually recreate those generated files.

## 6. Review the generated files

The important generated areas include:

- `README.md` and `LEAME.md`;
- `container_install.sh`;
- `install.sh` for the Django profile only;
- `Dockerfile`;
- `docker-compose.test.yml` and `docker-compose.prod.yml`;
- `conf/`;
- `scripts/container_start.sh` and `scripts/smoke_test.sh`;
- `.gitignore` and `.dockerignore`;
- `deployment/lib/`;
- `.bu-isciii-deployment/state.json`.

The exact files depend on the selected profile, services, and addons. Review [Generated project structure](../reference/generated-project-structure.md) for the full explanation.

## 7. Customize application-owned sections

Some generated files are fully managed by the standard. Others contain explicit `BU-ISCIII APPLICATION` blocks that the application may customize, and some generated configuration or code is application-owned. Modify only those intended extension points.

For example, keep an application-specific command inside the marked block rather than changing the managed shell logic around it:

```bash
# BEGIN BU-ISCIII APPLICATION
# Add application-specific commands here.
# END BU-ISCIII APPLICATION
```

Do not edit files under `deployment/lib/`; they are exact vendored copies of the shared deployment library. See [Scaffold workflow](scaffold-workflow.md) for ownership and future synchronization behavior.

## 8. Validate the baseline

After `init`, run the scaffold check:

```bash
python3 /path/to/buisciii-deployment-standards/scripts/scaffold.py \
  check /path/to/example-app
```

`check` is read-only and reports whether generated files, application-owned blocks, state metadata, and vendored libraries agree with the scaffold. Review any reported drift before committing. Runtime validation with Docker or Podman belongs to the later [Deployment workflow](deployment-workflow.md).

## 9. Commit the initial deployment baseline

Review the generated baseline, then commit it with the application repository:

```bash
git status
git add .
git commit -m "Add BU-ISCIII deployment baseline"
```

Do not commit production secrets or local runtime configuration.

## 10. Next steps

Continue with:

- [Configuration](configuration.md) to configure the application;
- [Scaffold workflow](scaffold-workflow.md) to understand future scaffold updates;
- [Docker Compose](docker-compose.md) to understand the generated Compose definitions;
