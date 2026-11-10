# ==============================================================================
# Multi-Stage Production Dockerfile for Hospital Management Platform (Django)
# Role: DevOps & Cloud Engineering
# Security Hardening: Non-root execution, minimal layers, pinned base image
# ==============================================================================

# ----------------- STAGE 1: Builder -----------------
FROM python:3.10-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Build dependencies for C-extensions (psycopg2, cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt


# ----------------- STAGE 2: Production Runtime -----------------
FROM python:3.10-slim-bookworm AS runner

LABEL maintainer="DevOps & Cloud Engineering Team" \
      service="hospital-appointment-api-django" \
      version="1.0.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:${PATH}" \
    DJANGO_SETTINGS_MODULE="core.settings"

# Install minimal runtime libraries and curl for healthcheck probes
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Create dedicated unprivileged user and group (Least Privilege)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m -d /home/appuser appuser

WORKDIR /home/appuser/app

# Install compiled wheels as non-root
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* && \
    rm -rf /wheels

# Copy application codebase
COPY --chown=appuser:appgroup manage.py .
COPY --chown=appuser:appgroup core/ ./core/
COPY --chown=appuser:appgroup appointments/ ./appointments/

# Create directory for staticfiles and sqlite/backups with permissions
RUN mkdir -p staticfiles backups && chown -R appuser:appgroup /home/appuser/app

# Switch to unprivileged user
USER appuser

# Expose internal API port
EXPOSE 8000

# Container Healthcheck (Liveness Probe)
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/liveness/ || exit 1

# Production WSGI server
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
