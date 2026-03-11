# ─── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml .
COPY alembic.ini .

# Create virtual environment and install dependencies from pyproject.toml
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache \
      "fastapi>=0.111.0" \
      "uvicorn[standard]>=0.29.0" \
      "sqlalchemy[asyncio]>=2.0.0" \
      "asyncpg>=0.29.0" \
      "alembic>=1.13.0" \
      "redis>=5.0.0" \
      "celery[redis]>=5.3.0" \
      "httpx>=0.27.0" \
      "pydantic>=2.7.0" \
      "pydantic-settings>=2.2.0" \
      "python-multipart>=0.0.9" \
      "qdrant-client>=1.9.0" \
      "python-jose[cryptography]>=3.3.0" \
      "passlib[bcrypt]>=1.7.4" \
      "psutil>=5.9.0"

# ─── Stage 2: Runner ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Activate virtual environment
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -u 1001 appuser

# Copy application code
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
