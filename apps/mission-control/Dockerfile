FROM node:22-alpine3.20@sha256:2289fb1fba0f4633b08ec47b94a89c7e20b829fc5679f9b7b298eaa2f1ed8b7e AS deps
WORKDIR /app
COPY package.json package-lock.json* .npmrc ./
# patches/ must be present before install so the postinstall patch-package step
# can apply the @lhci/utils js-yaml 4.x (safeLoad -> load) patch inside the image.
COPY patches ./patches
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:22-alpine3.20@sha256:2289fb1fba0f4633b08ec47b94a89c7e20b829fc5679f9b7b298eaa2f1ed8b7e AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_BUILD_TARGET=docker
RUN npm run build

FROM node:22-alpine3.20@sha256:2289fb1fba0f4633b08ec47b94a89c7e20b829fc5679f9b7b298eaa2f1ed8b7e AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
USER node
EXPOSE 3000
CMD ["npm", "run", "start"]
