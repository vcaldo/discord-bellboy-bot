# TTS Troubleshooting Guide

This guide helps resolve common Text-to-Speech issues with the Discord Bellboy Bot.

## Common Issues and Solutions

### 1. "Shard ID None heartbeat blocked for more than 20 seconds"

**Cause**: TTS model download is blocking Discord's event loop.

**Solution**:
- The bot now runs TTS initialization asynchronously with a 5-minute timeout
- If initialization fails, the bot continues without TTS functionality
- Use a faster model in `tts-config.yaml`:

```yaml
providers:
  coqui:
    model: "tts_models/en/ljspeech/tacotron2-DDC"  # Faster, smaller download
```

### 2. "Model download failed" or Network Issues

**Causes**:
- Network connectivity issues
- GitHub rate limiting
- Firewall blocking downloads

**Solutions**:
1. **Check internet connection**: Ensure the container/server has internet access
2. **Retry later**: GitHub may be rate limiting downloads
3. **Use pre-downloaded models**: Download models manually:
   ```bash
   python -c "from TTS.api import TTS; TTS('tts_models/en/ljspeech/tacotron2-DDC')"
   ```
4. **Alternative models**: Try different models in `tts-config.yaml`

### 3. "TTS not available" Message

**Cause**: Missing TTS dependencies.

**Solution**:
```bash
pip install TTS
```

### 4. "ffmpeg not found" Error

**Cause**: Missing ffmpeg for audio conversion.

**Solutions**:
- **Docker**: ffmpeg is included in the container
- **Local install**:
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Windows: Download from https://ffmpeg.org/

### 5. TTS Audio Not Playing

**Possible Causes**:
1. Bot not connected to voice channel
2. Missing Discord permissions
3. Audio file corruption

**Debugging Steps**:
1. Check logs for TTS generation errors
2. Verify bot has "Speak" permission in Discord
3. Test with debug logging: `LOG_LEVEL=DEBUG`

### 6. Slow TTS Generation

**Solutions**:
1. **Use faster model**:
   ```yaml
   model: "tts_models/en/ljspeech/tacotron2-DDC"
   ```
2. **Reduce audio quality**:
   ```yaml
   settings:
     audio_quality: "64k"  # Lower quality, faster processing
   ```
3. **Enable caching**: Ensure cache is enabled in config

## Model Recommendations

### Fast Models (Quick startup)
- `tts_models/en/ljspeech/tacotron2-DDC` - Good quality, fast
- `tts_models/en/ljspeech/speedy-speech` - Very fast, basic quality

### High Quality Models (Slower startup)
- `tts_models/en/ljspeech/fast_pitch` - High quality, moderate speed
- `tts_models/en/vctk/fast_pitch` - Multi-speaker, high quality

### Other Languages
- `tts_models/es/mai/tacotron2-DDC` - Spanish
- `tts_models/fr/mai/tacotron2-DDC` - French
- `tts_models/de/thorsten/tacotron2-DDC` - German

## Configuration Tips

### 1. Environment-Specific Settings

**Development** (fast startup):
```yaml
providers:
  coqui:
    model: "tts_models/en/ljspeech/tacotron2-DDC"
    settings:
      audio_quality: "64k"
```

**Production** (high quality):
```yaml
providers:
  coqui:
    model: "tts_models/en/ljspeech/fast_pitch"
    settings:
      audio_quality: "128k"
```

### 2. Cache Configuration

For high-traffic servers:
```yaml
cache:
  enabled: true
  max_files: 100  # Increase cache size
  directory: "/app/assets"
```

For limited storage:
```yaml
cache:
  enabled: true
  max_files: 20   # Smaller cache
  directory: "/tmp/tts_cache"
```

## Monitoring and Debugging

### 1. Enable Debug Logging
```bash
LOG_LEVEL=DEBUG python app/bellboy.py
```

### 2. Check TTS Initialization
Look for these log messages:
- `✓ "TTS Manager initialized successfully"`
- `✗ "TTS Manager initialization failed"`
- `⚠ "TTS functionality disabled"`

### 3. Monitor Performance
- Check TTS generation times in logs
- Monitor cache hit rates
- Watch for memory usage with large models

## Getting Help

If issues persist:

1. **Check logs**: Look in `logs/bellboy_YYYYMMDD.log`
2. **Test configuration**: Run `python test_tts_config.py`
3. **Verify requirements**: Ensure all dependencies are installed
4. **Report issues**: Include logs and configuration when reporting bugs

## Fallback Options

If TTS continues to fail:

1. **Disable TTS**: Set `TTS_PROVIDER=""` in `.env`
2. **Use different provider**: (When additional providers are added)
3. **Manual model setup**: Pre-download models before starting bot

The bot will always continue to function for voice channel monitoring even if TTS fails.
