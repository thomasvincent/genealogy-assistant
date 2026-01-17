# Genealogy Assistant Docker Image
# Multi-stage build for optimized image size

# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies including Gramps requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    # Gramps build dependencies
    libxml2-dev \
    libxslt1-dev \
    # For lxml compilation
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ src/

# Create virtual environment and install dependencies
RUN uv venv /app/.venv
RUN . /app/.venv/bin/activate && uv pip install -e ".[web]"

# Stage 2: Runtime
FROM python:3.12-slim as runtime

WORKDIR /app

# Install runtime dependencies for Gramps
RUN apt-get update && apt-get install -y --no-install-recommends \
    # XML processing (required by Gramps)
    libxml2 \
    libxslt1.1 \
    # GObject introspection (required by Gramps core)
    gir1.2-glib-2.0 \
    libgirepository-1.0-1 \
    # ICU for internationalization (optional but recommended)
    libicu72 \
    # For healthcheck
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and directories
RUN useradd --create-home --shell /bin/bash genai && \
    mkdir -p /app/data /app/logs && \
    chown -R genai:genai /app

USER genai

# Copy virtual environment from builder
COPY --from=builder --chown=genai:genai /app/.venv /app/.venv
COPY --from=builder --chown=genai:genai /app/src /app/src
COPY --chown=genai:genai pyproject.toml /app/

# Set environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV PYTHONUNBUFFERED=1

# Data volumes
VOLUME ["/app/data", "/app/logs"]

# Default command - run CLI
ENTRYPOINT ["python", "-m", "genealogy_assistant.cli"]
CMD ["--help"]

# Expose port for web API (if running FastAPI server)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import genealogy_assistant; print('OK')" || exit 1

# Labels
LABEL maintainer="Thomas Vincent"
LABEL description="AI-powered genealogy research assistant with Gramps integration"
LABEL version="0.1.0"
