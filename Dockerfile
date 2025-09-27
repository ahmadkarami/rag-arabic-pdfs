FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /opt/app

COPY ./src/requirements.txt ./

# Install Python dependencies
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --no-compile -r requirements.txt

FROM python:3.11-slim AS rag_server

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install poppler-utils (PDF tools like pdftoppm, pdftocairo)
RUN apt-get update \
    && apt-get install -y poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m appuser

# Copy over venv from builder
COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv
# Copy over the rest of the src folder
COPY --chown=appuser:appuser ./src/ /app/src/

USER appuser

# Copy over the entrypoint script
COPY --chown=appuser:appuser ./entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

# Set working directory to /app/src
WORKDIR /app/src

# Run the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]