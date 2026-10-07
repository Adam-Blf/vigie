# syntax=docker/dockerfile:1.12
# The Vigie PWA: a Vite build served by an unprivileged nginx on port 8080.
#
#   docker build -f deploy/docker/web.Dockerfile -t vigie-web:dev .
#
# The build stage runs on the builder's own platform: its output is static files, the
# same for amd64 and arm64, so emulating Node under QEMU would only cost time.

ARG NODE_IMAGE=docker.io/library/node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402
ARG NGINX_IMAGE=docker.io/nginxinc/nginx-unprivileged:1.30-alpine@sha256:15c994d10d6d78658721c3bcafff14cb281fba2a4bdf9d5ba92c416a472516e3

FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS build
WORKDIR /web
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit
COPY web/ ./
# The project script: typecheck, vite build, then the bundle size check.
RUN npm run build

FROM ${NGINX_IMAGE} AS runtime
USER 0
# The stock site and its IPv6 rewrite script both target /etc/nginx/conf.d, which is
# read-only at runtime; the Vigie site is rendered into /tmp instead.
RUN rm -f /etc/nginx/conf.d/default.conf /docker-entrypoint.d/10-listen-on-ipv6-by-default.sh
COPY deploy/docker/nginx/nginx.conf /etc/nginx/nginx.conf
COPY deploy/docker/nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY deploy/docker/nginx/default.conf.template /etc/nginx/templates/vigie/default.conf.template
COPY --from=build /web/dist /usr/share/nginx/html
USER 101
# In Kubernetes the ingress sends /v1 straight to the API, but nginx still resolves its
# upstream at start-up, so the default names a Service that exists there; compose sets
# api:8710.
ENV NGINX_ENVSUBST_OUTPUT_DIR=/tmp \
    NGINX_ENTRYPOINT_QUIET_LOGS=1 \
    VIGIE_API_UPSTREAM=vigie-api-stable:8710
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/"]
