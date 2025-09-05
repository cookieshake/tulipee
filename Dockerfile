FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

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
