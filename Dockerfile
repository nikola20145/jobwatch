FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so source edits don't bust the layer cache.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY migrations ./migrations

# Migrate, then poll forever. Override CMD with `jobwatch run` for a
# platform-scheduled one-shot instead of a long-running loop.
CMD ["sh", "-c", "alembic upgrade head && jobwatch run --loop"]
