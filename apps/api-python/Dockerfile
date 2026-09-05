FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS base

# Install uv package manager (pinned digest)
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:8b940d3a9d65bed080436972241af2e21c84b5e8c9193f7014ed71479ee795ff /uv /uvx /bin/

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
