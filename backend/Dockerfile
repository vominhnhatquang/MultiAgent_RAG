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

# Copy full source (needed by pyproject.toml install)
COPY . .

# Create virtual environment and install all deps from pyproject.toml
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache .

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
