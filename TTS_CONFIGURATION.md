# TTS Configuration Guide

This bot supports multiple Text-to-Speech (TTS) providers through a configurable system. The TTS provider and its settings are managed through environment variables and a YAML configuration file.

## Configuration

### Environment Variables

Set the `TTS_PROVIDER` environment variable to choose your TTS provider:

```bash
TTS_PROVIDER=coqui  # Currently supported: coqui
```

### TTS Configuration File

The `tts-config.yaml` file contains all provider-specific configurations:

```yaml
providers:
  coqui:
    name: "Coqui TTS"
    enabled: true
    model: "tts_models/en/ljspeech/fast_pitch"
    language: "en"
    settings:
      progress_bar: false
      output_format: "mp3"
      audio_quality: "128k"
      volume: "1.1"
    messages:
      join: "Bem vindo {display_name}"
      leave: "tchau tchau {display_name}"
      move: "trocou de canal {display_name}"

default_provider: "coqui"

cache:
  enabled: true
  max_files: 50
  directory: "/app/assets"
```

## Currently Supported Providers

### Coqui TTS
- **Provider ID**: `coqui`
- **Description**: Open-source TTS with multiple model support
- **Requirements**: `TTS` package
- **Installation**: `pip install TTS`

## Message Types

The TTS system supports three message types:

- **join**: Played when a user joins a voice channel
- **leave**: Played when a user leaves a voice channel
- **move**: Played when a user moves between voice channels

Each message type can use placeholders like `{display_name}` that will be replaced with actual values.

## Adding New Providers

To add a new TTS provider:

1. Create a new provider class inheriting from `TTSProvider` in `app/tts/tts_manager.py`
2. Implement the required abstract methods:
   - `provider_name`: Return the unique provider identifier
   - `initialize()`: Initialize the provider (async)
   - `synthesize()`: Generate audio from text (async)
3. Add the provider to the `providers` registry in `TTSManager.__init__()`
4. Add provider configuration to `tts-config.yaml`
5. Update this documentation

## Cache Management

The TTS system includes automatic cache management:

- Generated audio files are cached to improve performance
- Cache size is limited (configurable via `cache.max_files`)
- Oldest files are automatically removed when the cache is full
- Cache directory is configurable via `cache.directory`

## Troubleshooting

### TTS Not Working
1. Check that the required packages are installed
2. Verify the provider is enabled in `tts-config.yaml`
3. Check the logs for initialization errors
4. Ensure ffmpeg is available for audio conversion

### Audio Quality Issues
- Adjust the `audio_quality` setting in the provider configuration
- Try different models (for Coqui TTS)
- Check the `volume` setting in ffmpeg options

### Performance Issues
- Reduce cache size if disk space is limited
- Consider using faster TTS models
- Monitor TTS generation times in logs
