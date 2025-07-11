import discord
import logging
import os
from datetime import datetime
from typing import Optional, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

# Constants
LOGS_DIR = 'logs'
LOG_DATE_FORMAT = '%Y%m%d'
LOG_MESSAGE_FORMAT = '%(asctime)s | %(levelname)s | %(message)s'
AUDIO_FILE_PATH = '/app/assets/notification.mp3'

# FFmpeg options for audio playback
FFMPEG_OPTIONS = {
    'before_options': '-nostdin',
    'options': '-vn -filter:a "volume=0.7"'
}


class BellboyBot(discord.Client):
    """
    BellBoy Discord bot that:
    - Monitors voice channel activity
    - Joins the busiest voice channel when users join/leave/move
    - Leaves when no real users are present
    - Plays notification audio on voice activity
    """

    def __init__(self):
        # Set up intents
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.members = True

        super().__init__(intents=intents)

        # Set up logging
        self._setup_logging()
        self.logger = logging.getLogger('bellboy')

    def _setup_logging(self) -> None:
        """Set up logging to file and console."""
        # Create logs directory if it doesn't exist
        os.makedirs(LOGS_DIR, exist_ok=True)

        # Create logger
        logger = logging.getLogger('bellboy')
        logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()

        # File handler
        log_filename = f"bellboy_{datetime.now().strftime(LOG_DATE_FORMAT)}.log"
        log_filepath = os.path.join(LOGS_DIR, log_filename)
        file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(LOG_MESSAGE_FORMAT))
        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(LOG_MESSAGE_FORMAT))
        logger.addHandler(console_handler)

    def _safe_guild_name(self, guild: discord.Guild) -> str:
        """Get a safe representation of guild name for logging."""
        try:
            return guild.name
        except UnicodeEncodeError:
            return guild.name.encode('ascii', errors='replace').decode('ascii')
        except Exception:
            return f"Guild_{guild.id}"

    def _format_member_info(self, member: discord.Member) -> str:
        """Format member information for logging."""
        try:
            return f"{member.display_name} ({member.name}#{member.discriminator})"
        except Exception:
            return f"Member_{member.id}"

    def _count_human_members(self, channel: discord.VoiceChannel) -> int:
        """Count non-bot members in a voice channel."""
        return len([member for member in channel.members if not member.bot])

    def _is_monitoring_guild(self, guild: discord.Guild) -> bool:
        """Check if the bot should monitor this guild."""
        if GUILD_ID:
            try:
                return guild.id == int(GUILD_ID)
            except ValueError:
                return True
        return True

    async def find_busiest_voice_channel(self, guild: discord.Guild) -> Tuple[Optional[discord.VoiceChannel], int]:
        """
        Find the voice channel with the most human members.

        Returns:
            Tuple of (busiest_channel, member_count).
            Returns (None, 0) if no channels have members.
        """
        busiest_channel = None
        max_members = 0

        for channel in guild.voice_channels:
            member_count = self._count_human_members(channel)
            if member_count > max_members:
                max_members = member_count
                busiest_channel = channel

        return busiest_channel, max_members

    async def play_notification_audio(self, audio_path: str, guild: discord.Guild) -> None:
        """
        Play notification audio in the voice channel if bot is connected.

        Args:
            audio_path: Path to the MP3 file to play
            guild: Discord guild where the bot should play audio
        """
        try:
            # Check if bot is connected to a voice channel
            if not guild.voice_client or not guild.voice_client.is_connected():
                return

            # Check if audio file exists
            if not os.path.exists(audio_path):
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.warning(f"[{safe_guild_name}] Audio file not found: {audio_path}")
                return

            # Don't interrupt if already playing audio
            if guild.voice_client.is_playing():
                return

            # Create audio source and play
            try:
                audio_source = discord.FFmpegPCMAudio(audio_path, **FFMPEG_OPTIONS)
                guild.voice_client.play(
                    audio_source,
                    after=lambda e: self.logger.error(f'Audio player error: {e}') if e else None
                )

                safe_guild_name = self._safe_guild_name(guild)
                self.logger.debug(f"[{safe_guild_name}] Playing notification audio")
            except discord.errors.ClientException as e:
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.error(f"[{safe_guild_name}] Discord client error playing audio: {e}")
            except Exception as e:
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.error(f"[{safe_guild_name}] FFmpeg error playing audio: {e}")

        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Error playing notification audio: {e}")

    async def join_busiest_channel_if_needed(self, guild: discord.Guild) -> None:
        """Join the busiest voice channel if bot is not already there."""
        try:
            busiest_channel, max_members = await self.find_busiest_voice_channel(guild)

            # Only proceed if there are users in voice channels
            if not busiest_channel or max_members == 0:
                return

            # If bot is not connected, join the busiest channel
            if not guild.voice_client:
                await busiest_channel.connect()
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.info(f"[{safe_guild_name}] Bot joined busiest channel: {busiest_channel.name} ({max_members} members)")
                return

            # If bot is connected but not in the busiest channel, move there
            current_channel = guild.voice_client.channel
            if current_channel != busiest_channel:
                await guild.voice_client.move_to(busiest_channel)
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.info(f"[{safe_guild_name}] Bot moved to busier channel: {busiest_channel.name} ({max_members} members)")

        except discord.ClientException as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Discord client error joining voice channel: {e}")
        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Unexpected error joining voice channel: {e}")

    async def leave_if_empty(self, guild: discord.Guild) -> None:
        """Leave voice channel if no human members are present."""
        try:
            # Check if bot is connected
            if not guild.voice_client or not guild.voice_client.is_connected():
                return

            current_channel = guild.voice_client.channel
            human_count = self._count_human_members(current_channel)

            # Leave if no human members
            if human_count == 0:
                await guild.voice_client.disconnect()
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.info(f"[{safe_guild_name}] Bot left empty channel: {current_channel.name}")

        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Error checking if should leave empty channel: {e}")

    async def on_ready(self):
        """Called when the bot is ready."""
        self.logger.info(f'Bot logged in as {self.user} (ID: {self.user.id})')
        self.logger.info('Monitoring voice channel activity...')

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Called when a user's voice state changes."""
        # Skip if it's a bot
        if not self._is_monitoring_guild(member.guild) or member.bot:
            return

        username = self._format_member_info(member)
        safe_guild_name = self._safe_guild_name(member.guild)
        guild = member.guild

        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            self.logger.info(f"[{safe_guild_name}] {username} joined voice channel: {after.channel.name}")
            await self.play_notification_audio(AUDIO_FILE_PATH, guild)
            await self.join_busiest_channel_if_needed(guild)

        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            self.logger.info(f"[{safe_guild_name}] {username} left voice channel: {before.channel.name}")
            await self.play_notification_audio(AUDIO_FILE_PATH, guild)
            # await self.leave_if_empty(guild)

        # User moved between voice channels
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            self.logger.info(f"[{safe_guild_name}] {username} moved from {before.channel.name} to {after.channel.name}")
            await self.play_notification_audio(AUDIO_FILE_PATH, guild)
            await self.join_busiest_channel_if_needed(guild)
            # await self.leave_if_empty(guild)

    async def on_error(self, event, *args, **kwargs):
        """Called when an error occurs."""
        self.logger.error(f'An error occurred in event {event}', exc_info=True)


def main():
    """Main function to run the bot."""
    # Validate configuration
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN is required but not set in environment variables or .env file")
        return

    # Create and run the bot
    bot = BellboyBot()

    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("Error: Invalid Discord token. Please check your DISCORD_TOKEN in .env file.")
    except KeyboardInterrupt:
        print("Bot shutdown requested by user.")
    except Exception as e:
        print(f"Error running bot: {e}")
        logging.getLogger('bellboy').error(f"Fatal error running bot: {e}", exc_info=True)


if __name__ == "__main__":
    main()
