# Discord Bellboy Bot

A Discord bot that monitors voice channel activity and provides intelligent TTS notifications with multi-provider support.

## Features

- **Voice Channel Monitoring**: Automatically joins the busiest voice channel
- **Smart TTS Notifications**: Announces when users join, leave, or move between channels
- **Multi-Provider TTS Support**: Configurable TTS providers (currently supports Coqui TTS)
- **Intelligent Behavior**: Only follows real users, ignores bots and applications
- **New Relic Integration**: Optional monitoring and performance tracking
- **Configurable Messages**: Customize TTS announcements via YAML configuration
- **Automatic Caching**: Efficient TTS file management with automatic cleanup

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/vcaldo/discord-bellboy-bot.git
cd discord-bellboy-bot

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your Discord token
DISCORD_TOKEN=your_discord_bot_token_here
TTS_PROVIDER=coqui
```

### 3. Run the Bot

```bash
python app/bellboy.py
```

Or using Docker:

```bash
docker-compose up --build
```

## TTS Configuration

The bot uses a flexible TTS system configured via `tts-config.yaml`:

```yaml
providers:
  coqui:
    name: "Coqui TTS"
    enabled: true
    model: "tts_models/en/ljspeech/fast_pitch"
    messages:
      join: "Bem vindo {display_name}"
      leave: "tchau tchau {display_name}"
      move: "trocou de canal {display_name}"

default_provider: "coqui"
```

### Supported Providers

- **Coqui TTS**: Open-source TTS with multiple model support
- *More providers coming soon*: ElevenLabs, Azure, Google Cloud, Amazon Polly

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_TOKEN` | Your Discord bot token | Required |
| `TTS_PROVIDER` | TTS provider to use | `coqui` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `SPECIAL_USERS` | Comma-separated Discord user IDs for alternate messages | Optional |
| `NEW_RELIC_LICENSE_KEY` | New Relic monitoring (optional) | Disabled |

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Copy the bot token to your `.env` file
4. Invite the bot to your server with these permissions:
   - Connect to voice channels
   - Speak in voice channels
   - View channels
   - Read message history

## Documentation

- [Setup Guide](SETUP_GUIDE.md) - Detailed installation and configuration
- [TTS Configuration](TTS_CONFIGURATION.md) - TTS provider configuration guide
- [TTS Troubleshooting](TTS_TROUBLESHOOTING.md) - Common issues and solutions
- [New Relic Setup](NEW_RELIC_SETUP.md) - Monitoring configuration

## Development

### Project Structure

```
discord-bellboy-bot/
├── app/
│   ├── bellboy.py          # Main bot application
│   └── tts/
│       ├── __init__.py
│       └── tts_manager.py  # TTS provider management
├── tts-config.yaml         # TTS configuration
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Docker setup
└── Dockerfile             # Container definition
```

### Adding New TTS Providers

1. Create a new provider class in `app/tts/tts_manager.py`
2. Inherit from `TTSProvider` and implement required methods
3. Add provider to the registry in `TTSManager`
4. Update `tts-config.yaml` with provider configuration

### Testing

```bash
# Validate TTS configuration
python test_tts_config.py

# Run with debug logging
LOG_LEVEL=DEBUG python app/bellboy.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

- Check the [logs](logs/) directory for detailed error information
- Review the setup guides for common issues
- Open an issue on GitHub for bugs or feature requests
