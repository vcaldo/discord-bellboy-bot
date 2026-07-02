FROM python:3.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install runtime dependencies required for Discord voice playback
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsodium23 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Upgrade pip to ensure prebuilt wheels are preferred over source builds
RUN pip install --upgrade pip

# Install all Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Copy New Relic configuration
COPY newrelic.ini .

# Create logs directory
RUN mkdir -p logs

# Create assets directory for cached TTS files
RUN mkdir -p assets

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app

# Switch to non-root user
USER app

# Health check — verifies the bot event loop is alive and Discord is connected
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python healthcheck.py || exit 1

# Command to run the application with New Relic monitoring
CMD ["newrelic-admin", "run-program", "python", "bellboy.py"]
