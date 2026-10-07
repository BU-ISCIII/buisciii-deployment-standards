# Configuration Matrix Template

Application/environment:

Never put real secret values in this document.

| Variable or setting | Owner | Required | Secret | Build/runtime | Scope | Test default | Production source | Notes |
|---|---|---:|---:|---|---|---|---|---|
| | | | | | | | | |

Scope should be one of:

- public: used by a browser or external client;
- host: resolved from the deployment host;
- internal: resolved only inside the service network;
- local: limited to a process or component.

## Cross-service invariants

Record values that must agree across services, for example:

| Contract | Producer | Consumers | Validation |
|---|---|---|---|
| Identity issuer | Identity provider | APIs and web | Compare discovery metadata with configured issuer |
| API audience | Identity provider | API | Decode a token and perform an authenticated request |
| Public API URL | Reverse proxy | Web/browser | Load application and inspect a real API request |

