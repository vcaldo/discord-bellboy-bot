# Discord Bellboy Bot - TTS Provider Setup

This guide will help you set up and run the Discord Bellboy Bot with the new multi-provider TTS system.

## Quick Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

Edit `.env` and set your Discord token:
```bash
DISCORD_TOKEN=your_actual_discord_token_here
TTS_PROVIDER=coqui
```

### 3. Configure TTS (Optional)

The bot comes with a default `tts-config.yaml` file. You can customize:

- TTS messages (join/leave/move announcements)
- Audio quality settings
- Cache configuration
- Provider-specific settings

### 4. Run the Bot

```bash
python app/bellboy.py
```

Or using the Docker setup:

```bash
docker-compose up --build
```

## TTS Provider Configuration

### Current Provider: Coqui TTS

The bot currently supports Coqui TTS as the default provider. The configuration in `tts-config.yaml` includes:

- **Model**: `tts_models/en/ljspeech/fast_pitch` (English, fast generation)
- **Messages**: Portuguese announcements by default
- **Audio Quality**: 128k MP3 output
- **Cache**: Automatic cleanup of old TTS files

### Customizing Messages

Edit the `messages` section in `tts-config.yaml`:

```yaml
providers:
  coqui:
    messages:
      join: "Welcome {display_name}"        # User joins channel
      leave: "Goodbye {display_name}"       # User leaves channel
      move: "Moved channels {display_name}" # User moves between channels
```

### Environment Variables

- `TTS_PROVIDER`: Set to `coqui` (more providers coming soon)
- `DISCORD_TOKEN`: Your Discord bot token
- `LOG_LEVEL`: Logging level (INFO, DEBUG, WARNING, ERROR)

## Testing the Setup

Run the validation script to check your configuration:

```bash
python test_tts_config.py
```

This will verify:
- Configuration file is valid
- TTS manager can be created
- Providers are properly configured

## Troubleshooting

### Common Issues

1. **"TTS not available"**: Install TTS package with `pip install TTS`
2. **"FFmpeg not found"**: Install FFmpeg for audio conversion
3. **"Config file not found"**: Ensure `tts-config.yaml` is in the root directory
4. **Import errors during development**: Normal if packages aren't installed in your IDE environment

### Logs

Check the logs directory for detailed error information:
- `logs/bellboy_YYYYMMDD.log`

### Discord Permissions

Ensure your bot has these permissions:
- Connect to voice channels
- Speak in voice channels
- View channels
- Read message history

## Future Providers

The system is designed to support additional TTS providers. Planned additions:

- ElevenLabs API
- Azure Cognitive Services
- Google Cloud Text-to-Speech
- Amazon Polly

Each provider will have its own configuration section in `tts-config.yaml` and can be switched via the `TTS_PROVIDER` environment variable.
