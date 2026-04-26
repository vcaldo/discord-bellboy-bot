# TTS Configuration Guide

Discord Bellboy Bot uses Microsoft Edge TTS for all voice announcements.

## Configuration

TTS settings are managed in `tts-config.yaml`:

```yaml
providers:
  edge:
    name: "Edge TTS"
    enabled: true
    voice: "pt-PT-DuarteNeural"
    settings:
      output_format: "mp3"
    messages:
      join:
        - "Bem vindo {display_name}"
      leave:
        - "Falou {display_name}, ate mais"
      move:
        - "O tal do {display_name} trocou de canal"

cooldown_seconds: 60

cache:
  enabled: true
  max_size_mb: 1024
  directory: "/app/assets"
```

## Edge TTS

- **Provider**: Microsoft Edge TTS via the `edge-tts` package
- **Audio format**: MP3
- **Voice**: Controlled by `providers.edge.voice`
- **Provider selection**: Not configurable; Edge TTS is always used

You can change the voice by setting another Edge neural voice in `tts-config.yaml`.

## Message Types

The TTS system supports three message types:

- **join**: Played when a user joins a voice channel
- **leave**: Played when a user leaves a voice channel
- **move**: Played when a user moves between voice channels

Each message can use placeholders like `{display_name}`. A message type can be either a string or a list of strings; lists rotate between available messages.

## Special User Messages

You can define alternate messages for specific users by adding `_alt` message types:

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

Then set `SPECIAL_USERS` with comma-separated Discord user IDs:

```bash
SPECIAL_USERS=123456789012345678,987654321098765432
```

When a user in `SPECIAL_USERS` joins, leaves, or moves, the bot uses the `_alt` message if it exists. Otherwise, it falls back to the regular message.

## Cache Management

Generated MP3 files are cached to improve performance:

- Cache size is limited by `cache.max_size_mb`
- Cache directory is configured by `cache.directory`
- Oldest cached files are removed automatically when the size limit is exceeded
- `TTS_CACHE_MAX_SIZE_MB` can override the configured cache size

## Troubleshooting

### TTS Not Working

1. Check that `edge-tts` is installed.
2. Verify `providers.edge.enabled` is `true` in `tts-config.yaml`.
3. Ensure the configured Edge voice name is valid.
4. Check the logs for initialization or synthesis errors.

### Audio Playback Issues

- Ensure `ffmpeg` is installed and available in the runtime.
- Confirm the bot has Discord voice permissions to connect and speak.
- Check that the cache directory is writable.
