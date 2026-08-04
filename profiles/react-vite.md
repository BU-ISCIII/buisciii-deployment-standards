# React and Vite Profile

Use this profile for browser applications built with React and Vite.

## Required considerations

- Documentation MUST distinguish build-time `VITE_*` values from runtime
  configuration. Recreating a container without rebuilding does not change
  values compiled into a bundle.
- Browser-facing URLs MUST be publicly resolvable URLs, not container service
  names.
- Internal reverse-proxy targets MUST be documented separately from public API
  URLs.
- Production builds MUST use the intended production mode and MUST NOT embed
  secrets; browser bundles cannot safely contain secrets.
- Client-side routes MUST fall back to the application entry point where
  appropriate.
- Cache behavior for versioned assets and the HTML entry point SHOULD be
  documented.
- The smoke test MUST load the application and verify at least one real API
  request. Authenticated applications MUST also verify login redirection and
  return from the identity provider.

