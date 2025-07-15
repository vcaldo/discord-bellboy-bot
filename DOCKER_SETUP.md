# Docker Setup Guide

This guide explains how to run the Discord Bellboy Bot using Docker with custom configurations.

## Quick Start

### 1. Basic Setup

```bash
# Clone and navigate to the repository
git clone https://github.com/vcaldo/discord-bellboy-bot.git
cd discord-bellboy-bot

# Copy environment file and configure
cp .env.example .env
# Edit .env with your Discord token and settings

# Start the bot
docker-compose up -d
```

### 2. View Logs

```bash
# Follow logs in real-time
docker-compose logs -f

# View logs from a specific time
docker-compose logs --since="1h"
```

## Configuration Management

### Environment Variables

The main configuration is through environment variables in `.env`:

```bash
# Required
DISCORD_TOKEN=your_discord_bot_token_here
GUILD_ID=your_guild_id_here

# TTS Configuration
TTS_PROVIDER=coqui

# Optional
LOG_LEVEL=INFO
NEW_RELIC_LICENSE_KEY=your_key_here
```

### TTS Configuration File

The TTS system is configured via `tts-config.yaml`:

#### Default Location
The file is automatically mounted from the project root:
```yaml
# docker-compose.yml
volumes:
  - ./tts-config.yaml:/app/tts-config.yaml:ro
```

#### Custom Configuration
To use a different config file:

1. **Create your custom config:**
   ```bash
   cp tts-config.yaml my-custom-tts.yaml
   # Edit my-custom-tts.yaml with your settings
   ```

2. **Update docker-compose.yml:**
   ```yaml
   volumes:
     - ./my-custom-tts.yaml:/app/tts-config.yaml:ro
   ```

3. **Or use docker-compose.override.yml:**
   ```yaml
   # docker-compose.override.yml
   services:
     discord-bellboy-bot:
       volumes:
         - ./my-custom-tts.yaml:/app/tts-config.yaml:ro
   ```

## Persistent Storage

### Volumes

The setup includes several volumes for persistent data:

```yaml
volumes:
  - ./logs:/app/logs              # Log files on host
  - tts-cache:/app/assets         # TTS cache (Docker volume)
  - ./.env:/app/.env:ro           # Environment config
  - ./tts-config.yaml:/app/tts-config.yaml:ro  # TTS config
```

### Cache Management

#### Default (Docker Volume)
TTS files are cached in a Docker volume:
```yaml
volumes:
  - tts-cache:/app/assets
```

**Pros:** Managed by Docker, doesn't clutter host filesystem
**Cons:** Harder to inspect or manage manually

#### Host Directory Cache
To store cache on the host filesystem:

```yaml
# docker-compose.override.yml
services:
  discord-bellboy-bot:
    volumes:
      - ./tts-cache:/app/assets
```

**Pros:** Easy to inspect, backup, or clear cache manually
**Cons:** Takes up space in project directory

### Cache Commands

```bash
# View cache size (Docker volume)
docker system df -v

# Clear TTS cache (Docker volume)
docker volume rm discord-bellboy-bot_tts-cache

# Clear TTS cache (host directory)
rm -rf ./tts-cache/*
```

## Development Setup

### Development Override

Create `docker-compose.override.yml` for development:

```yaml
services:
  discord-bellboy-bot:
    environment:
      - LOG_LEVEL=DEBUG
    volumes:
      # Live reload app code
      - ./app:/app/app:ro
      # Use host directory for cache
      - ./dev-cache:/app/assets
    restart: "no"
```

### Development Commands

```bash
# Build and start with debug logging
LOG_LEVEL=DEBUG docker-compose up --build

# Run without restart policy (for development)
docker-compose up --no-deps discord-bellboy-bot

# Shell into running container
docker-compose exec discord-bellboy-bot bash

# Run one-off commands
docker-compose run --rm discord-bellboy-bot python test_tts_config.py
```

## Customization Examples

### 1. Multiple Environment Configurations

#### Production (docker-compose.prod.yml)
```yaml
services:
  discord-bellboy-bot:
    environment:
      - LOG_LEVEL=INFO
      - NEW_RELIC_ENVIRONMENT=production
    volumes:
      - /var/log/bellboy:/app/logs
      - /etc/bellboy/tts-config.yaml:/app/tts-config.yaml:ro
    restart: always
```

Run with: `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

#### Development (docker-compose.dev.yml)
```yaml
services:
  discord-bellboy-bot:
    environment:
      - LOG_LEVEL=DEBUG
      - NEW_RELIC_ENVIRONMENT=development
    volumes:
      - ./app:/app/app:ro
      - ./dev-tts-config.yaml:/app/tts-config.yaml:ro
    restart: "no"
```

Run with: `docker-compose -f docker-compose.yml -f docker-compose.dev.yml up`

### 2. Custom TTS Configurations

#### Fast/Lightweight Config
```yaml
# tts-config-fast.yaml
providers:
  coqui:
    model: "tts_models/en/ljspeech/tacotron2-DDC"
    settings:
      audio_quality: "64k"
cache:
  max_files: 20
```

#### High Quality Config
```yaml
# tts-config-hq.yaml
providers:
  coqui:
    model: "tts_models/en/ljspeech/fast_pitch"
    settings:
      audio_quality: "192k"
cache:
  max_files: 100
```

### 3. Network Configuration

#### Custom Network
```yaml
# docker-compose.yml
networks:
  bellboy-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

#### External Network
```yaml
# docker-compose.yml
networks:
  external-network:
    external: true

services:
  discord-bellboy-bot:
    networks:
      - external-network
```

## Troubleshooting

### Common Issues

#### 1. Config File Not Found
```bash
# Error: tts-config.yaml not found
# Solution: Ensure file exists in project root
ls -la tts-config.yaml
```

#### 2. Permission Issues
```bash
# Error: Permission denied for mounted files
# Solution: Check file permissions
chmod 644 tts-config.yaml .env
```

#### 3. TTS Cache Issues
```bash
# Error: Cannot write to cache directory
# Solution: Check volume permissions or recreate volume
docker-compose down
docker volume rm discord-bellboy-bot_tts-cache
docker-compose up -d
```

### Debug Commands

```bash
# Check container status
docker-compose ps

# View detailed logs
docker-compose logs --timestamps discord-bellboy-bot

# Inspect container configuration
docker-compose config

# Check mounted volumes
docker inspect discord-bellboy-bot_discord-bellboy-bot_1 | grep -A 10 "Mounts"

# Test TTS configuration
docker-compose exec discord-bellboy-bot python test_tts_config.py
```

### Health Checks

Add health checks to monitor the bot:

```yaml
# docker-compose.yml
services:
  discord-bellboy-bot:
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8080/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## Security Considerations

### File Permissions
```bash
# Secure environment file
chmod 600 .env

# Read-only config files
chmod 644 tts-config.yaml
```

### Secrets Management
For production, consider using Docker secrets:

```yaml
services:
  discord-bellboy-bot:
    secrets:
      - discord_token
    environment:
      - DISCORD_TOKEN_FILE=/run/secrets/discord_token

secrets:
  discord_token:
    file: ./secrets/discord_token.txt
```

This setup provides flexible configuration management while maintaining security and ease of use.
