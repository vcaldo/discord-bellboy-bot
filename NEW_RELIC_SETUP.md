# New Relic Monitoring Setup

This Discord bot is instrumented with New Relic for comprehensive application monitoring, performance tracking, and error reporting.

## Getting Started with New Relic

1. **Create a New Relic Account**: Sign up at [https://newrelic.com](https://newrelic.com)

2. **Get Your License Key**:
   - Go to [API Keys](https://one.newrelic.com/launcher/api-keys-ui.api-keys-launcher)
   - Copy your License Key (starts with `NRAL-`)

3. **Configure Environment Variables**:
   ```bash
   # Required
   NEW_RELIC_LICENSE_KEY=your_license_key_here

   # Optional (with defaults)
   NEW_RELIC_APP_NAME=Discord-Bellboy-Bot
   NEW_RELIC_ENVIRONMENT=production
   ```

## Monitored Metrics

The bot tracks the following custom metrics:

### Discord Activity
- `Custom/Discord/VoiceStateUpdates` - Total voice state changes
- `Custom/Discord/HumanVoiceActivity` - Human user voice activity
- `Custom/Discord/BotVoiceActivity` - Bot voice activity (filtered out)
- `Custom/Discord/UserJoined` - Users joining voice channels
- `Custom/Discord/UserLeft` - Users leaving voice channels
- `Custom/Discord/UserMoved` - Users moving between channels
- `Custom/Discord/Errors` - Discord API errors

### Text-to-Speech (TTS)
- `Custom/TTS/Requests` - TTS generation requests
- `Custom/TTS/Success` - Successful TTS generations
- `Custom/TTS/Errors/NotInitialized` - TTS not available
- `Custom/TTS/Errors/Generation` - TTS generation failures
- `Custom/TTS/Errors/FFmpeg` - Audio conversion failures
- `Custom/TTS/Errors/Timeout` - TTS generation timeouts

### Audio Playback
- `Custom/Audio/PlaybackAttempts` - Audio playback attempts
- `Custom/Audio/PlaybackSuccess` - Successful audio playback
- `Custom/Audio/NotConnected` - Bot not connected to voice
- `Custom/Audio/FileNotFound` - Audio file missing
- `Custom/Audio/AlreadyPlaying` - Audio already playing
- `Custom/Audio/DiscordClientError` - Discord audio errors
- `Custom/Audio/FFmpegError` - FFmpeg audio errors

### Bot Health
- `Custom/Bot/Startup` - Bot startup events
- `Custom/Bot/LoginFailure` - Authentication failures
- `Custom/Bot/ManualShutdown` - Manual shutdowns
- `Custom/Bot/FatalError` - Fatal errors

## Function-Level Tracing

The following functions are instrumented with detailed tracing:
- `create_tts_mp3()` - TTS generation and audio conversion
- `create_and_play_tts()` - Complete TTS workflow
- `play_notification_audio()` - Audio playback
- `on_voice_state_update()` - Voice activity handling

## Error Tracking

All exceptions are automatically captured and sent to New Relic with:
- Full stack traces
- Custom attributes (guild info, user info, etc.)
- Error categorization by component (TTS, Audio, Discord)

## Custom Attributes

Each transaction includes relevant context:
- Guild ID and name
- User ID and display name
- Voice channel information
- File paths and TTS text
- Audio configuration

## Configuration Options

### Environment Variables (Recommended)
```bash
NEW_RELIC_LICENSE_KEY=your_license_key
NEW_RELIC_APP_NAME=Your-Bot-Name
NEW_RELIC_ENVIRONMENT=production|staging|development
```

### Configuration File (Alternative)
Set `NEW_RELIC_CONFIG_FILE=/app/newrelic.ini` to use the included configuration file.

## Monitoring Dashboard

After deployment, view your bot's performance at:
- [New Relic One](https://one.newrelic.com)
- APM → Your App Name
- Custom metrics under "Data explorer"

## Troubleshooting

1. **No data appearing**: Verify your license key and check logs for New Relic initialization messages

2. **Missing custom metrics**: Ensure the bot is processing voice activities to generate metrics

3. **High error rates**: Check the "Errors" section in New Relic APM for detailed error analysis

## Privacy and Security

- No sensitive user data (tokens, personal info) is sent to New Relic
- Only functional metrics and error information are transmitted
- All data transmission is encrypted
- You can disable monitoring by not setting `NEW_RELIC_LICENSE_KEY`
