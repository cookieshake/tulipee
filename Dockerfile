FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv (fast Python package manager) and ca-certs
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Sync dependencies into a local virtualenv using the lockfile (no dev deps)
RUN uv sync --frozen --no-dev && \
    . .venv/bin/activate && \
    python -V

# Add application source
COPY tulipee ./tulipee
COPY README.md ./

# Create a non-root user and adjust ownership
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Ensure the virtualenv is used
ENV PATH="/app/.venv/bin:${PATH}"

CMD ["python", "-m", "tulipee"]
