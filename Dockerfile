# Use Python 3.11 instead of 3.12 for better compatibility
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies required for PyNaCl, discord.py, and Coqui TTS
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    libsodium-dev \
    ffmpeg \
    alsa-utils \
    libsndfile1 \
    libsndfile1-dev \
    build-essential \
    python3-dev \
    git \
    pkg-config \
    libssl-dev \
    libavcodec-dev \
    libavformat-dev \
    libavdevice-dev \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install all Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Copy New Relic configuration
COPY newrelic.ini .

# Create logs directory
RUN mkdir -p logs

# Create assets directory for TTS files
RUN mkdir -p assets

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app

# Switch to non-root user
USER app

# Health check to ensure the bot is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Command to run the application with New Relic monitoring
CMD ["newrelic-admin", "run-program", "python", "bellboy.py"]
