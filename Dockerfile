# Stage 1: build the React frontend.
FROM node:20-alpine AS webbuild
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY web/ ./
RUN npm run build

# Stage 2: the Python app, carrying only the built frontend (no Node).
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so source edits don't bust the layer cache.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY migrations ./migrations
COPY --from=webbuild /web/dist ./web/dist

# Migrate, then poll forever. Override CMD with `jobwatch run` for a
# platform-scheduled one-shot, or `jobwatch serve --host 0.0.0.0 --port 8000`
# to run the dashboard as its own service.
CMD ["sh", "-c", "alembic upgrade head && jobwatch run --loop"]
