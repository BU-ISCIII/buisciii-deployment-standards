# syntax=docker/dockerfile:1.4
FROM docker.io/library/node:22-bookworm-slim AS deps

WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund --prefer-offline --fetch-retries=3 --fetch-timeout=60000

FROM deps AS build

ARG GIT_REVISION=current
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_MEPRAM_API_BASE_URL
ARG NEXT_PUBLIC_KEYCLOAK_URL
ARG NEXT_PUBLIC_KEYCLOAK_REALM
ARG NEXT_PUBLIC_KEYCLOAK_CLIENT_ID
ARG NEXT_PUBLIC_USE_CASE_DATA_MODE=live
ARG NEXT_PUBLIC_USE_CASE_ALERTS_CONTACT_EMAIL
ARG AUTH_SECRET=build-only-placeholder
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_MEPRAM_API_BASE_URL=${NEXT_PUBLIC_MEPRAM_API_BASE_URL} \
    NEXT_PUBLIC_KEYCLOAK_URL=${NEXT_PUBLIC_KEYCLOAK_URL} \
    NEXT_PUBLIC_KEYCLOAK_REALM=${NEXT_PUBLIC_KEYCLOAK_REALM} \
    NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=${NEXT_PUBLIC_KEYCLOAK_CLIENT_ID} \
    NEXT_PUBLIC_USE_CASE_DATA_MODE=${NEXT_PUBLIC_USE_CASE_DATA_MODE} \
    NEXT_PUBLIC_USE_CASE_ALERTS_CONTACT_EMAIL=${NEXT_PUBLIC_USE_CASE_ALERTS_CONTACT_EMAIL} \
    AUTH_SECRET=${AUTH_SECRET}

COPY . ./
RUN npm run build && printf '%s\n' "${GIT_REVISION}" > .next/.deployed_revision

FROM docker.io/library/node:22-bookworm-slim AS prod

WORKDIR /app
ENV NODE_ENV=production APP_PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/package*.json ./
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/.next ./.next
COPY --from=build --chown=node:node /app/public ./public
COPY scripts/container_start.sh /usr/local/bin/container_start.sh

USER node:node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "require('http').get('http://127.0.0.1:' + process.env.APP_PORT + '/health/',r=>process.exit(r.statusCode>=200&&r.statusCode<400?0:1)).on('error',()=>process.exit(1))"
CMD ["/usr/local/bin/container_start.sh"]
