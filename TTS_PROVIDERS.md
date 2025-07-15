# TTS Provider Configuration Guide

This document describes how to configure and use the different TTS providers available in the Discord Bellboy Bot.

## Overview

The bot now supports multiple TTS providers with a provider-based architecture:
- **Coqui TTS**: High-quality neural TTS with many models
- **Piper TTS**: Fast, lightweight local TTS
- **MeloTTS**: Multilingual TTS with natural voices

## Environment Variables

### General TTS Configuration

```bash
# TTS Provider to use (coqui, piper, melo)
TTS_PROVIDER=coqui

# Cache settings
TTS_CACHE_SIZE=50
```

### Coqui TTS Configuration

```bash
# Coqui TTS model to use
TTS_MODEL=tts_models/en/ljspeech/fast_pitch

# Language for TTS
TTS_LANGUAGE=en

# Whether to show progress bar during model loading
TTS_PROGRESS_BAR=false

# Whether to use GPU for inference (requires CUDA)
TTS_GPU=false
```

### Piper TTS Configuration

```bash
# Path to Piper ONNX model file
PIPER_MODEL_PATH=/app/models/piper/en_US-lessac-medium.onnx

# Speaker ID for multi-speaker models
PIPER_SPEAKER_ID=0

# Speech rate control (1.0 = normal, 0.5 = slower, 2.0 = faster)
PIPER_LENGTH_SCALE=1.0

# Voice noise/variation controls
PIPER_NOISE_SCALE=0.667
PIPER_NOISE_W=0.8

# Audio sample rate
PIPER_SAMPLE_RATE=22050
```

### MeloTTS Configuration

```bash
# Language for MeloTTS (EN, ES, FR, ZH, JP, KR)
MELO_LANGUAGE=EN

# Device to use (auto, cpu, cuda)
MELO_DEVICE=auto

# Speaker ID
MELO_SPEAKER_ID=EN-Default

# Speech speed (1.0 = normal)
MELO_SPEED=1.0

# Audio sample rate
MELO_SAMPLE_RATE=44100
```

## Installation

### Base Requirements

```bash
pip install discord.py python-dotenv PyNaCl numpy soundfile
```

### Coqui TTS (Default)

```bash
pip install TTS==0.17.8
```

### Piper TTS

```bash
pip install piper-tts
```

You'll also need to download model files:
```bash
# Example: Download English model
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

### MeloTTS

```bash
pip install melo-tts
```

## Usage Examples

### Basic Usage (Code)

```python
from app.tts.tts_manager import TTSManager
import logging

# Initialize with default provider
logger = logging.getLogger(__name__)
tts_manager = TTSManager(logger)

# Check if TTS is available
if tts_manager.is_available:
    # Generate TTS
    success = tts_manager.create_tts_mp3("Hello world", "/tmp/hello.mp3")

    # Get provider info
    info = tts_manager.get_provider_info()
    print(f"Using provider: {info['name']}")
```

### Switch Providers

```python
# Switch to Piper TTS
success = tts_manager.switch_provider("piper")
if success:
    print("Switched to Piper TTS")

# Switch to MeloTTS
success = tts_manager.switch_provider("melo")
if success:
    print("Switched to MeloTTS")
```

### List Available Providers

```python
providers = tts_manager.list_available_providers()
for provider, available in providers.items():
    print(f"{provider}: {'✓' if available else '✗'}")
```

## Provider Comparison

| Provider | Speed | Quality | Size | Languages | GPU Support |
|----------|-------|---------|------|-----------|-------------|
| Coqui TTS | Medium | High | Large | Many | Yes |
| Piper TTS | Fast | Good | Small | Many | No |
| MeloTTS | Medium | High | Medium | 6 | Yes |

## Troubleshooting

### Provider Not Available

If a provider shows as not available:

1. **Check installation**: Ensure the provider library is installed
2. **Check models**: Ensure model files exist (especially for Piper)
3. **Check configuration**: Verify environment variables are set correctly
4. **Check logs**: Look for initialization errors in the bot logs

### Common Issues

**Coqui TTS**:
- Model download may take time on first run
- Large models require significant RAM
- GPU support requires CUDA installation

**Piper TTS**:
- Requires model files to be downloaded separately
- Model path must be absolute and accessible
- Limited to specific model formats (ONNX)

**MeloTTS**:
- May download models on first use
- Language support depends on available models
- Newer library, may have compatibility issues

### Performance Tips

1. **Use Piper for speed**: Best for real-time applications
2. **Use Coqui for quality**: Best for high-quality generation
3. **Cache aggressively**: Set higher `TTS_CACHE_SIZE` for frequently used phrases
4. **GPU acceleration**: Enable for Coqui TTS if available

## Docker Configuration

When using Docker, ensure model files are properly mounted:

```yaml
services:
  bellboy:
    volumes:
      - ./models:/app/models  # For Piper models
    environment:
      - TTS_PROVIDER=piper
      - PIPER_MODEL_PATH=/app/models/piper/en_US-lessac-medium.onnx
```
