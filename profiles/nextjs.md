# Next.js Profile

Use this profile for React applications that require a persistent Next.js Node
server rather than a static browser bundle.

## Required considerations

- Public `NEXT_PUBLIC_*` values are embedded during `next build`, are visible to
  browsers, and require an image rebuild when changed.
- Secrets and internal service targets MUST be supplied only to the runtime
  container. They MUST NOT use the `NEXT_PUBLIC_` prefix.
- Production runs as an unprivileged Node user with `NODE_ENV=production` and
  `next start`.
- The image health check MUST exercise the running HTTP server.
- Applications using server-side authentication, route handlers, middleware,
  or proxy routes MUST document their public callback URL and internal targets.
- Writable Next.js cache data is ephemeral unless an application explicitly
  documents and mounts it as persistent state.
