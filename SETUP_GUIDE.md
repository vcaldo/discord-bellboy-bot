# Discord Bellboy Bot - Setup Guide

This guide helps you set up and run Discord Bellboy Bot with Edge TTS voice announcements.

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

Set your Discord bot token:

```bash
DISCORD_TOKEN=your_actual_discord_token_here
```

### 3. Configure TTS

The bot uses Edge TTS only. Customize `tts-config.yaml` to change:

- Edge voice
- Join, leave, and move announcement messages
- Special-user alternate messages
- Cache size and directory
- Salute cooldown

### 4. Run the Bot

```bash
python app/bellboy.py
```

Or using Docker:

```bash
docker-compose up --build
```

## TTS Configuration

### Provider: Edge TTS

The bot uses Microsoft Edge TTS via the `edge-tts` package as its only speech engine.

The default `tts-config.yaml` includes:

- **Voice**: `pt-PT-DuarteNeural`
- **Messages**: Portuguese announcements by default
- **Audio format**: MP3
- **Cache**: Automatic cleanup of old TTS files

### Customizing Messages

Edit the `messages` section in `tts-config.yaml`:

```yaml
providers:
  edge:
    messages:
      join: "Welcome {display_name}"
      leave: "Goodbye {display_name}"
      move: "Moved channels {display_name}"
      join_alt: "The boss {display_name} has arrived!"
      leave_alt: "The boss {display_name} has left!"
      move_alt: "The boss {display_name} switched channels!"
```

### Special User Messages

You can configure special messages for specific users:

1. Add alternate message types ending with `_alt` to `tts-config.yaml`.
2. Set `SPECIAL_USERS` with Discord user IDs:

```bash
SPECIAL_USERS=123456789012345678,987654321098765432
```

To get a Discord user ID:

1. Enable Developer Mode in Discord (User Settings -> Advanced -> Developer Mode).
2. Right-click the user and select "Copy ID".

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DISCORD_TOKEN` | Your Discord bot token | Required |
| `LOG_LEVEL` | Logging level (`INFO`, `DEBUG`, `WARNING`, `ERROR`) | `INFO` |
| `SPECIAL_USERS` | Comma-separated Discord user IDs for alternate messages | Optional |
| `IGNORED_USERS` | Comma-separated Discord user IDs to never announce | Optional |
| `IGNORED_CHANNEL_ID` | Voice channel ID to ignore when selecting busiest channel | Optional |
| `SALUTE_COOLDOWN_SECONDS` | Override the TTS salute cooldown | `tts-config.yaml` |
| `TTS_CACHE_MAX_SIZE_MB` | Override the generated audio cache size | `tts-config.yaml` |

## Troubleshooting

### Common Issues

1. **"edge-tts not available"**: Install dependencies with `pip install -r requirements.txt`.
2. **"FFmpeg error playing audio"**: Install FFmpeg for Discord audio playback.
3. **"Config file not found"**: Ensure `tts-config.yaml` is in the repository root when running locally or mounted in Docker.
4. **No voice announcements**: Confirm `providers.edge.enabled` is `true` and the bot has Connect/Speak permissions.

### Logs

Check the logs directory for detailed error information:

- `logs/bellboy_YYYYMMDD.log`

### Discord Permissions

Ensure your bot has these permissions:

- Connect to voice channels
- Speak in voice channels
- View channels
- Read message history
