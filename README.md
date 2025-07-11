# Discord Bellboy Bot

A Discord bot that monitors voice channel activity and provides intelligent TTS notifications using Coqui TTS.

## Features

- Logs when users join or leave the Discord server
- Logs when users join, leave, or move between voice channels
- **Automatically joins the busiest voice channel** when voice activity changes
- **Automatically leaves empty voice channels** when no users remain
- **Plays TTS notifications** using Coqui TTS when users join, leave, or move between voice channels
- **High-quality text-to-speech** with configurable voice models
- **Smart TTS caching** to improve performance and manage disk space
- Configurable through environment variables or `.env` file
- Supports monitoring specific guilds or all guilds
- Structured logging with file and console output

## TTS Features

- **Coqui TTS Integration**: High-quality, open-source text-to-speech
- **Multiple Voice Models**: Choose from fast, high-quality, and multi-speaker models
- **Multi-language Support**: English, Spanish, French, German, and more
- **Automatic Caching**: Smart cache management for generated TTS files
- **Configurable Models**: Easy model switching via environment variables

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note**: The bot requires PyNaCl for voice functionality, FFmpeg for audio processing, and Coqui TTS for text-to-speech generation.

**System Dependencies:**
- **FFmpeg**: For audio processing and conversion
  - **Windows**: Download from https://ffmpeg.org/download.html and add to PATH
  - **Linux**: `sudo apt install ffmpeg libsndfile1` (Ubuntu/Debian) or equivalent
  - **macOS**: `brew install ffmpeg` (with Homebrew)

**Python Dependencies:**
- `discord.py`: Discord API wrapper
- `python-dotenv`: Environment variable management
- `PyNaCl`: Voice functionality
- `TTS`: Coqui TTS for high-quality text-to-speech
- `numpy`: Numerical computing for TTS
- `soundfile`: Audio file I/O

### 2. Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section
4. Create a bot and copy the token
5. Enable the following privileged intents:
   - Server Members Intent (for member join/leave events)
   - Message Content Intent (if you plan to add commands)

### 3. Configure the Bot

Copy the `.env.example` to `.env` and fill in your configuration:

```env
# Discord Bot Configuration
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_server_id_here  # Optional: leave empty to monitor all servers
LOG_LEVEL=INFO

# Coqui TTS Configuration
TTS_MODEL=tts_models/en/ljspeech/fast_pitch  # Fast, good quality model
TTS_CACHE_SIZE=50  # Number of TTS files to keep cached
```

#### Available TTS Models

**Fast Models (Recommended for real-time use):**
- `tts_models/en/ljspeech/fast_pitch` - Default, fast and good quality
- `tts_models/en/ljspeech/glow-tts` - Alternative fast model

**High Quality Models (Slower):**
- `tts_models/en/ljspeech/tacotron2-DDC` - Higher quality, slower
- `tts_models/en/ljspeech/vits` - VITS model, very high quality

**Multi-speaker Models:**
- `tts_models/en/vctk/vits` - Multiple English voices
- `tts_models/en/sam/tacotron-DDC` - Alternative multi-speaker

**Other Languages:**
- `tts_models/es/mai/tacotron2-DDC` - Spanish
- `tts_models/fr/mai/tacotron2-DDC` - French
- `tts_models/de/thorsten/tacotron2-DDC` - German

### 4. Invite the Bot to Your Server

Create an invite link with the following permissions:
- View Channels
- Connect (for voice channel monitoring)
- Use Voice Activity (for voice channel monitoring)
- Send Messages (for bot commands)
- Use Slash Commands (for bot commands)

Bot permissions integer: `3146752`

Example invite URL:
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=3145728&scope=bot
```

### 5. Add Audio File (Optional)

To enable notification sounds when users join/leave/move in voice channels:

1. Add your audio file to `app/assets/notification.mp3`
2. Recommended format: MP3, 1-3 seconds duration
3. Test with the `!test_audio` command

See `app/assets/README.md` for detailed audio specifications.

### 6. Test TTS Functionality (Optional)

Before running the bot, you can test if Coqui TTS is working correctly:

```bash
python test_coqui_tts.py
```

This will:
- Initialize the TTS model
- Generate a test audio file
- List available TTS models
- Verify the installation is working correctly

If the test fails, check that:
- All system dependencies (FFmpeg, libsndfile1) are installed
- The TTS model name in your `.env` file is correct
- You have sufficient disk space for model downloads

### 7. Run the Bot

```bash
python bot.py
```

### 8. Docker Setup (Alternative)

```bash
# Build the Docker image
docker build -t discord-bellboy-bot .

# Run the container with environment file
docker run -d --name bellboy-bot --env-file .env discord-bellboy-bot

# Or run with environment variables directly
docker run -d --name bellboy-bot \
  -e DISCORD_TOKEN=your_token_here \
  -e GUILD_ID=your_guild_id \
  -e TTS_MODEL=tts_models/en/ljspeech/fast_pitch \
  discord-bellboy-bot
```

**Note**: The bot will automatically detect if TTS is available and gracefully disable TTS features if the installation fails during the Docker build.

## Bot Commands

The bot includes several commands for manual control:

- `!join_busiest` - Manually make the bot join the busiest voice channel
- `!leave_voice` - Make the bot leave the current voice channel
- `!voice_status` - Show current voice channel status and bot configuration
- `!check_busiest` - Check and display the busiest voice channel without joining
- `!test_audio` - Test the notification audio (requires bot to be in voice channel)

## Voice Channel Behavior

The bot automatically:
1. **Monitors voice activity** - Tracks when users join, leave, or move between channels
2. **Finds the busiest channel** - Counts active members (excluding bots) in each voice channel
3. **Joins strategically** - Connects to the busiest channel only when:
   - Someone joins a voice channel AND
   - The bot is not already connected to a voice channel
4. **Leaves when empty** - Automatically disconnects when all users leave the bot's current channel
5. **Plays notification audio** - Plays a sound when users join, leave, or move between channels (if audio file is configured)
6. **Stays put otherwise** - Once connected, the bot remains in place unless the channel empties
7. **Manual control** - Use commands to manually move or disconnect the bot

This behavior prevents the bot from constantly moving between channels and only makes it join when there's new voice activity.

**Note**: Both behaviors can be controlled via `.env` settings:
- `AUTO_JOIN_BUSIEST=false` - Disable automatic joining
- `AUTO_LEAVE_EMPTY=false` - Disable automatic leaving

## Configuration

The bot reads configuration from environment variables or a `.env` file:

- `DISCORD_TOKEN` (required): Your Discord bot token
- `GUILD_ID` (optional): Specific Discord server ID to monitor. Leave empty to monitor all servers
- `LOG_LEVEL` (optional): Logging level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO
- `AUTO_JOIN_BUSIEST` (optional): Whether bot should automatically join the busiest voice channel (true/false). Defaults to true
- `AUTO_LEAVE_EMPTY` (optional): Whether bot should automatically leave empty voice channels (true/false). Defaults to true

## Logs

Logs are saved to the `logs/` directory with the filename format `bellboy_YYYYMMDD.log` and also displayed in the console.

Log format:
```
YYYY-MM-DD HH:MM:SS,mmm | LEVEL | MESSAGE
```

Example log entries:
```
2025-07-11 10:30:15,123 | INFO | [My Server] JohnDoe (johndoe#1234) joined voice channel: General
2025-07-11 10:31:20,456 | INFO | [My Server] JohnDoe (johndoe#1234) moved from General to Music
2025-07-11 10:32:10,789 | INFO | [My Server] JohnDoe (johndoe#1234) left voice channel: Music
```

## Project Structure

```
discord-bellboy-bot/
├── bot.py              # Main bot file
├── config.py           # Configuration management
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (create from .env.example)
├── logs/              # Log files directory (created automatically)
└── README.md          # This file
```
