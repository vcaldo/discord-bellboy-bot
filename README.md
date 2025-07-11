# Discord Bellboy Bot

A Discord bot that logs user activities including joining/leaving servers and voice channel movements.

## Features

- Logs when users join or leave the Discord server
- Logs when users join, leave, or move between voice channels
- Configurable through environment variables or `.env` file
- Supports monitoring specific guilds or all guilds
- Structured logging with file and console output

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section
4. Create a bot and copy the token
5. Enable the following privileged intents:
   - Server Members Intent (for member join/leave events)
   - Message Content Intent (if you plan to add commands)

### 3. Configure the Bot

Copy the `.env.example` to `.env` and fill in your bot token:

```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_server_id_here  # Optional: leave empty to monitor all servers
LOG_LEVEL=INFO
```

### 4. Invite the Bot to Your Server

Create an invite link with the following permissions:
- View Channels
- Connect (for voice channel monitoring)
- Use Voice Activity (for voice channel monitoring)

Bot permissions integer: `3145728`

Example invite URL:
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=3145728&scope=bot
```

### 5. Run the Bot

```bash
python bot.py
```

## Configuration

The bot reads configuration from environment variables or a `.env` file:

- `DISCORD_TOKEN` (required): Your Discord bot token
- `GUILD_ID` (optional): Specific Discord server ID to monitor. Leave empty to monitor all servers
- `LOG_LEVEL` (optional): Logging level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO

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
