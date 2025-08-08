# Frontend Dockerfile (monorepo-aware)
FROM node:20-alpine AS base

# Install redis-cli (provided by the 'redis' package on Alpine)
RUN apk add --no-cache redis

# Install pnpm
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate

# Build args
ARG APP_DIR=apps/frontend

# Dependencies stage
FROM base AS deps
WORKDIR /app

# Copy workspace files and lockfile from monorepo root
# IMPORTANT: build with monorepo root as context
COPY pnpm-workspace.yaml ./pnpm-workspace.yaml
COPY package.json ./package.json
COPY pnpm-lock.yaml ./pnpm-lock.yaml

# Make sure the app's manifest exists at its workspace path
ARG APP_DIR=apps/frontend
RUN mkdir -p ${APP_DIR}
COPY ${APP_DIR}/package.json ${APP_DIR}/package.json

# Install only the frontend workspace with the frozen root lockfile
RUN pnpm --filter @vulcan/frontend install --frozen-lockfile

# Development stage
FROM base AS development
WORKDIR /app/apps/frontend

# Bring over node_modules and lockfile context from deps
COPY --from=deps /app /app

# Copy the app source
ARG APP_DIR=apps/frontend
COPY ${APP_DIR}/ .

EXPOSE 3000
CMD ["pnpm", "dev"]

# Builder stage
FROM base AS builder
WORKDIR /app/apps/frontend

COPY --from=deps /app /app
ARG APP_DIR=apps/frontend
COPY ${APP_DIR}/ .

# Build the application
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

# Production stage
FROM base AS production
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup -g 1001 -S nodejs && adduser -S -u 1001 -G nodejs nextjs

# Copy built application
COPY --from=builder /app/apps/frontend/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/apps/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/frontend/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
