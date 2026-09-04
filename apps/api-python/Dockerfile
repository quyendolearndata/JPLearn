FROM python:3.12-slim AS base

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=3002

# Create non-root system user
RUN useradd -u 10001 -d /app -s /bin/sh appuser

# Copy dependency specifications
COPY pyproject.toml uv.lock README.md ./

# Install project dependencies into /app/.venv without dev dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code and configuration
COPY alembic.ini ./alembic.ini
COPY src/ ./src/

# Install the application wheel into the virtualenv
RUN uv sync --frozen --no-dev

# Setup persistent storage directory and ownership
RUN mkdir -p /app/storage && chown -R appuser:appuser /app

USER appuser

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 3002

CMD ["uvicorn", "jplearn_api.main:app", "--host", "0.0.0.0", "--port", "3002"]
