FROM node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0

# vitest (and the TypeScript it transpiles with) installed from the committed
# lockfile, so every transitive dependency is pinned and integrity-checked by
# npm ci. /node_modules is linked at the filesystem root: Node resolves bare
# imports by walking up from the importing file, so a test anywhere under
# /tmp finds `vitest` without a node_modules of its own.
WORKDIR /opt/factory/node
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund && npm cache clean --force \
    && ln -s /opt/factory/node/node_modules /node_modules
COPY run-tests /opt/factory/run-tests
RUN chmod 0555 /opt/factory/run-tests
WORKDIR /

LABEL org.opencontainers.image.title="thefactory sandbox-test-node" \
      org.opencontainers.image.description="Offline vitest / node:test runner for JavaScript and TypeScript runtime QC"
