# Developer Onboarding Guide

Last updated: 2026-03-02

## Goal

A new developer should be able to set up and validate the stack in under 2 hours.

## Prerequisites

- Windows with Docker Desktop and Compose v2.
- Python 3.11+.
- Node.js 20+ and npm.
- Git access to repository.

## Setup Steps

1. Clone repository and open terminal in root.
2. Copy environment template:
   - `cp .env.example .env`
3. Build and start core stack:
   - `docker compose -f deploy/docker-compose.yaml up -d --build`
4. Verify service health:
   - `http://localhost:8100/health`
   - `http://localhost:8101/health`
   - `http://localhost:8180/health`
   - `http://localhost:8102/health`
5. Validate Python dependencies and tests:
   - `python -m pytest -q`
6. Validate frontend:
   - `cd apps/mission-control`
   - `npm install`
   - `npm run build`
   - `npm run lint`

## Day-1 Commands

- `make validate`
- `make lint`
- `make test`
- `make audit`
- `make sweep`

## Common Troubleshooting

- Redis unavailable:
  - Check `docker compose ps`
  - Check Redis healthcheck status and logs.
- Gateway 503:
  - Ensure orchestrator and redis are healthy.
- Frontend API issues:
  - Verify `NEXT_PUBLIC_API_BASE_URL` in `.env`.
