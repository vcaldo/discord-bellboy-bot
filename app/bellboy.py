import discord
import logging
import os
from datetime import datetime
from typing import Optional, Tuple
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Initialize New Relic with defensive approach
import newrelic.agent

# Get New Relic configuration
NEW_RELIC_LICENSE_KEY = os.getenv('NEW_RELIC_LICENSE_KEY')
NEW_RELIC_APP_NAME = os.getenv('NEW_RELIC_APP_NAME', 'Discord-Bellboy-Bot')
NEW_RELIC_ENVIRONMENT = os.getenv('NEW_RELIC_ENVIRONMENT', 'production')

if NEW_RELIC_LICENSE_KEY:
    # When using newrelic-admin run-program, the agent is automatically initialized
    # We just need to register the application and verify it's working
    try:
        app = newrelic.agent.register_application(timeout=10.0)
        if app:
            print(f"New Relic application registered: {NEW_RELIC_APP_NAME}")
            print(f"New Relic application object: {app}")
        else:
            print("New Relic application registration failed")
    except Exception as e:
        print(f"New Relic application registration error: {e}")
        print("Continuing without New Relic monitoring...")
else:
    print("New Relic license key not found - monitoring disabled")

# Import TTS manager
from tts.tts_manager import TTSManager

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

# Constants
LOGS_DIR = 'logs'
LOG_DATE_FORMAT = '%Y%m%d'
LOG_MESSAGE_FORMAT = '%(asctime)s | %(levelname)s | %(message)s'

# FFmpeg options for audio playback
FFMPEG_OPTIONS = {
    'before_options': '-nostdin',
    'options': '-vn -filter:a "volume=1.1"'
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

        # Initialize TTS Manager
        self.tts_manager = TTSManager(self.logger)

        # Log TTS provider information
        if self.tts_manager.is_available:
            provider_info = self.tts_manager.get_provider_info()
            self.logger.info(f"TTS Provider initialized: {provider_info['name']}")
            self.logger.info(f"Supported formats: {provider_info['supported_formats']}")
        else:
            self.logger.warning("No TTS providers available - TTS functionality disabled")
            available_providers = self.tts_manager.list_available_providers()
            self.logger.info(f"Provider status: {available_providers}")

        # Test New Relic transaction
        if NEW_RELIC_LICENSE_KEY:
            self._test_newrelic_transaction()

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
        """Count non-bot members in a voice channel, excluding all bots and applications."""
        if channel is None:
            return 0

        # Filter out bots, applications, and the bot itself
        human_members = [member for member in channel.members if self._is_human_member(member)]

        member_names = [m.display_name for m in human_members]
        self.logger.debug(f"Channel '{channel.name}' has {len(human_members)} human members: {member_names}")
        return len(human_members)

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

    @newrelic.agent.function_trace()
    async def play_notification_audio(self, audio_path: str, guild: discord.Guild) -> None:
        """
        Play notification audio in the voice channel if bot is connected.

        Args:
            audio_path: Path to the MP3 file to play
            guild: Discord guild where the bot should play audio
        """
        try:
            # Add custom attributes for monitoring
            newrelic.agent.add_custom_attributes({
                'audio.path': audio_path,
                'guild.id': guild.id,
                'guild.name': self._safe_guild_name(guild)
            })

            # Record audio playback attempt
            newrelic.agent.record_custom_metric('Custom/Audio/PlaybackAttempts', 1)

            # Check if bot is connected to a voice channel
            if not guild.voice_client or not guild.voice_client.is_connected():
                newrelic.agent.record_custom_metric('Custom/Audio/NotConnected', 1)
                return

            # Check if audio file exists
            if not os.path.exists(audio_path):
                newrelic.agent.record_custom_metric('Custom/Audio/FileNotFound', 1)
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.warning(f"[{safe_guild_name}] Audio file not found: {audio_path}")
                return

            # Don't interrupt if already playing audio
            if guild.voice_client.is_playing():
                newrelic.agent.record_custom_metric('Custom/Audio/AlreadyPlaying', 1)
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
                newrelic.agent.record_custom_metric('Custom/Audio/PlaybackSuccess', 1)

            except discord.errors.ClientException as e:
                newrelic.agent.record_custom_metric('Custom/Audio/DiscordClientError', 1)
                newrelic.agent.notice_error()
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.error(f"[{safe_guild_name}] Discord client error playing audio: {e}")
            except Exception as e:
                newrelic.agent.record_custom_metric('Custom/Audio/FFmpegError', 1)
                newrelic.agent.notice_error()
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.error(f"[{safe_guild_name}] FFmpeg error playing audio: {e}")

        except Exception as e:
            newrelic.agent.record_custom_metric('Custom/Audio/GeneralError', 1)
            newrelic.agent.notice_error()
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
                self.logger.debug(f"[{self._safe_guild_name(guild)}] Bot not connected to any voice channel")
                return

            current_channel = guild.voice_client.channel

            # Add a small delay to ensure discord state is updated
            import asyncio
            await asyncio.sleep(0.5)

            human_count = self._count_human_members(current_channel)

            safe_guild_name = self._safe_guild_name(guild)
            self.logger.debug(f"[{safe_guild_name}] Checking if should leave {current_channel.name}: {human_count} human members")

            # Leave if no human members
            if human_count == 0:
                await guild.voice_client.disconnect()
                self.logger.info(f"[{safe_guild_name}] Bot left empty channel: {current_channel.name}")
            else:
                self.logger.debug(f"[{safe_guild_name}] Staying in {current_channel.name} with {human_count} human members")

        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Error checking if should leave empty channel: {e}")

    def _wrap_discord_event(self, event_name: str):
        """Decorator to wrap Discord events as New Relic transactions."""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                with newrelic.agent.BackgroundTask(application=newrelic.agent.application(), name=f'Discord.{event_name}'):
                    return await func(*args, **kwargs)
            return wrapper
        return decorator

    @newrelic.agent.background_task(name='Discord.on_ready')
    async def on_ready(self):
        """Called when the bot is ready."""
        self.logger.info(f'Bot logged in as {self.user} (ID: {self.user.id})')
        self.logger.info('Monitoring voice channel activity...')

        # Check if bot should join any channels on startup
        await self._check_initial_voice_channels()

    async def _check_initial_voice_channels(self) -> None:
        """Check all guilds for voice channels with users and join the busiest one if needed."""
        try:
            # Record startup voice channel check
            newrelic.agent.record_custom_metric('Custom/Bot/StartupChannelCheck', 1)

            for guild in self.guilds:
                try:
                    # Skip if not monitoring this guild
                    if not self._is_monitoring_guild(guild):
                        continue

                    safe_guild_name = self._safe_guild_name(guild)

                    # Find the busiest voice channel
                    busiest_channel, max_members = await self.find_busiest_voice_channel(guild)

                    # Join if there are users in voice channels and bot is not connected
                    if busiest_channel and max_members > 0 and not guild.voice_client:
                        try:
                            await busiest_channel.connect()
                            self.logger.info(f"[{safe_guild_name}] Bot joined channel on startup: {busiest_channel.name} ({max_members} members)")
                            newrelic.agent.record_custom_metric('Custom/Bot/StartupChannelJoin', 1)
                        except discord.ClientException as e:
                            self.logger.error(f"[{safe_guild_name}] Failed to join channel on startup: {e}")
                            newrelic.agent.record_custom_metric('Custom/Bot/StartupChannelJoinError', 1)
                    elif busiest_channel and max_members > 0:
                        self.logger.info(f"[{safe_guild_name}] Found active channel on startup: {busiest_channel.name} ({max_members} members) - already connected")
                    else:
                        self.logger.debug(f"[{safe_guild_name}] No active voice channels found on startup")

                except Exception as e:
                    safe_guild_name = self._safe_guild_name(guild)
                    self.logger.error(f"[{safe_guild_name}] Error checking voice channels on startup: {e}")
                    newrelic.agent.notice_error()

        except Exception as e:
            self.logger.error(f"Error during startup voice channel check: {e}")
            newrelic.agent.notice_error()

    @newrelic.agent.background_task(name='Discord.on_voice_state_update')
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Called when a user's voice state changes."""
        try:
            # Add custom attributes for monitoring
            newrelic.agent.add_custom_attributes({
                'guild.id': member.guild.id,
                'guild.name': self._safe_guild_name(member.guild),
                'member.id': member.id,
                'member.name': member.display_name,
                'member.is_bot': member.bot
            })

            # Record voice activity metrics
            newrelic.agent.record_custom_metric('Custom/Discord/VoiceStateUpdates', 1)

            # Skip if not monitoring this guild
            if not self._is_monitoring_guild(member.guild):
                return

            # Skip if it's not a human member (bots, apps, system users, etc.)
            if not self._is_human_member(member):
                newrelic.agent.record_custom_metric('Custom/Discord/BotVoiceActivity', 1)
                return

            # Record human voice activity
            newrelic.agent.record_custom_metric('Custom/Discord/HumanVoiceActivity', 1)

            username = self._format_member_info(member)
            safe_guild_name = self._safe_guild_name(member.guild)
            guild = member.guild

            # User joined a voice channel
            if before.channel is None and after.channel is not None:
                newrelic.agent.record_custom_metric('Custom/Discord/UserJoined', 1)
                newrelic.agent.add_custom_attributes({
                    'action': 'joined',
                    'channel.name': after.channel.name
                })

                self.logger.info(f"[{safe_guild_name}] {username} joined voice channel: {after.channel.name}")
                # Generate TTS audio for user joining
                tts_audio_path = self.tts_manager.create_user_join_tts(member.display_name, member.id)
                if tts_audio_path:
                    await self.play_notification_audio(tts_audio_path, guild)
                await self.join_busiest_channel_if_needed(guild)

            # User left a voice channel
            elif before.channel is not None and after.channel is None:
                newrelic.agent.record_custom_metric('Custom/Discord/UserLeft', 1)
                newrelic.agent.add_custom_attributes({
                    'action': 'left',
                    'channel.name': before.channel.name
                })

                self.logger.info(f"[{safe_guild_name}] {username} left voice channel: {before.channel.name}")
                # Generate TTS audio for user left
                tts_audio_path = self.tts_manager.create_user_leave_tts(member.display_name, member.id)
                if tts_audio_path:
                    await self.play_notification_audio(tts_audio_path, guild)
                await self.leave_if_empty(guild)

            # User moved between voice channels
            elif before.channel is not None and after.channel is not None and before.channel != after.channel:
                newrelic.agent.record_custom_metric('Custom/Discord/UserMoved', 1)
                newrelic.agent.add_custom_attributes({
                    'action': 'moved',
                    'from_channel.name': before.channel.name,
                    'to_channel.name': after.channel.name
                })

                self.logger.info(f"[{safe_guild_name}] {username} moved from {before.channel.name} to {after.channel.name}")
                tts_audio_path = self.tts_manager.create_user_move_tts(member.display_name, member.id)
                if tts_audio_path:
                    await self.play_notification_audio(tts_audio_path, guild)
                await self.join_busiest_channel_if_needed(guild)
                await self.leave_if_empty(guild)

        except Exception as e:
            newrelic.agent.record_custom_metric('Custom/Discord/VoiceStateUpdateErrors', 1)
            newrelic.agent.notice_error()
            safe_guild_name = self._safe_guild_name(member.guild)
            self.logger.error(f"[{safe_guild_name}] Error in voice state update: {e}")

    @newrelic.agent.background_task(name='Discord.on_error')
    async def on_error(self, event, *args, **kwargs):
        """Called when an error occurs."""
        # Record error metrics in New Relic
        newrelic.agent.record_custom_metric('Custom/Discord/Errors', 1)
        newrelic.agent.notice_error()

        self.logger.error(f'An error occurred in event {event}', exc_info=True)

    def _is_human_member(self, member: discord.Member) -> bool:
        """Check if a member is a real human user (not bot, app, or system user)."""
        # Skip if it's a bot
        if member.bot:
            return False

        # Skip if it's the bot itself (extra safety check)
        if self.user and member.id == self.user.id:
            return False

        # Skip if it's a system user or application (if the attribute exists)
        if hasattr(member, 'system') and member.system:
            return False

        # Skip if it's a webhook user
        if hasattr(member, 'discriminator') and member.discriminator == '0000':
            return False

        return True

    @newrelic.agent.background_task(name='Discord.Bot.TestTransaction')
    def _test_newrelic_transaction(self):
        """Test function to verify New Relic is working."""
        try:
            newrelic.agent.record_custom_metric('Custom/Bot/TestTransaction', 1)
            newrelic.agent.add_custom_attributes({
                'test.status': 'success',
                'test.timestamp': datetime.now().isoformat()
            })
            self.logger.info("New Relic test transaction recorded successfully")
        except Exception as e:
            self.logger.error(f"New Relic test transaction failed: {e}")

@newrelic.agent.background_task(name='Discord.Bot.Main')
def main():
    """Main function to run the bot."""
    # Validate configuration
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN is required but not set in environment variables or .env file")
        return

    # Create and run the bot
    bot = BellboyBot()

    try:
        # Record bot startup
        newrelic.agent.record_custom_metric('Custom/Bot/Startup', 1)
        newrelic.agent.add_custom_attributes({
            'bot.environment': NEW_RELIC_ENVIRONMENT,
            'bot.app_name': NEW_RELIC_APP_NAME
        })
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        newrelic.agent.record_custom_metric('Custom/Bot/LoginFailure', 1)
        newrelic.agent.notice_error()
        print("Error: Invalid Discord token. Please check your DISCORD_TOKEN in .env file.")
    except KeyboardInterrupt:
        newrelic.agent.record_custom_metric('Custom/Bot/ManualShutdown', 1)
        print("Bot shutdown requested by user.")
    except Exception as e:
        newrelic.agent.record_custom_metric('Custom/Bot/FatalError', 1)
        newrelic.agent.notice_error()
        print(f"Error running bot: {e}")
        logging.getLogger('bellboy').error(f"Fatal error running bot: {e}", exc_info=True)


if __name__ == "__main__":
    main()
