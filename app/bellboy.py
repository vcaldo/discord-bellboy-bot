import discord
import logging
import os
import subprocess
import tempfile
import asyncio
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

# Try to import TTS, but make it optional
try:
    from tts import TTSManager
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    TTSManager = None

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
TTS_PROVIDER = os.getenv('TTS_PROVIDER', 'coqui')  # Default to coqui

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

        # Initialize Coqui TTS
        self._init_tts()

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

    def _init_tts(self) -> None:
        """Initialize TTS manager."""
        # Check if TTS is available
        if not TTS_AVAILABLE:
            self.logger.warning("TTS module not available - TTS functionality will be disabled")
            self.logger.info("Install TTS dependencies with: pip install TTS PyYAML")
            self.tts_manager = None
            return

        try:
            # Initialize TTS manager with configured provider
            self.logger.info(f"Initializing TTS Manager with provider: {TTS_PROVIDER}")
            self.tts_manager = TTSManager(provider_name=TTS_PROVIDER)

            # Initialize asynchronously - we'll do this in the ready event
            self.logger.info("TTS Manager created, will initialize on bot ready")

        except Exception as e:
            self.logger.error(f"Failed to create TTS Manager: {e}")
            self.logger.warning("TTS functionality will be disabled")
            self.tts_manager = None

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
        return True

    @newrelic.agent.function_trace()
    async def create_and_play_tts(self, message_type: str, guild: discord.Guild, **kwargs) -> None:
        """
        Create a TTS audio from a message type and play it in the current voice channel.

        Args:
            message_type: The type of message (join, leave, move)
            guild: Discord guild where the audio should be played
            **kwargs: Additional parameters for message formatting
        """
        try:
            # Check if TTS is available
            if not self.tts_manager or not self.tts_manager.is_available:
                self.logger.debug(f"[{self._safe_guild_name(guild)}] TTS not available for message: {message_type}")
                return

            # Generate a unique cache path for this message
            member_id = kwargs.get('member_id', 'unknown')
            cache_path = self.tts_manager.generate_cache_path(
                f"{message_type}_{member_id}",
                prefix=f"msg_{message_type}"
            )

            # Log TTS request
            display_name = kwargs.get('display_name', 'Unknown')
            self.logger.debug(f"[{self._safe_guild_name(guild)}] TTS request: {message_type} for {display_name}")

            # Create the TTS audio
            success = await self.tts_manager.synthesize_message(message_type, cache_path, **kwargs)

            if success:
                # Play the generated TTS audio
                await self.play_notification_audio(cache_path, guild)
            else:
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.error(f"[{safe_guild_name}] Failed to create TTS for message type: {message_type}")

        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Error in create_and_play_tts: {e}")

    @newrelic.agent.function_trace()
    async def create_tts_from_text(self, text: str, guild: discord.Guild, **kwargs) -> None:
        """
        Create a TTS audio from arbitrary text and play it in the current voice channel.

        Args:
            text: The text to convert to speech and play
            guild: Discord guild where the audio should be played
            **kwargs: Additional parameters for TTS synthesis
        """
        try:
            # Check if TTS is available
            if not self.tts_manager or not self.tts_manager.is_available:
                self.logger.debug(f"[{self._safe_guild_name(guild)}] TTS not available for text: {text}")
                return

            # Generate a unique cache path for this text
            cache_path = self.tts_manager.generate_cache_path(text, prefix="custom")

            # Create the TTS audio
            success = await self.tts_manager.synthesize_text(text, cache_path, **kwargs)

            if success:
                # Play the generated TTS audio
                await self.play_notification_audio(cache_path, guild)
            else:
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.error(f"[{safe_guild_name}] Failed to create TTS for text: {text}")

        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Error in create_tts_from_text: {e}")

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

            # Check if bot is connected to a voice channel with robust checking
            if not guild.voice_client:
                newrelic.agent.record_custom_metric('Custom/Audio/NotConnected', 1)
                self.logger.debug(f"[{self._safe_guild_name(guild)}] No voice client available for audio playback")
                return

            # Additional connection state checks
            if not guild.voice_client.is_connected():
                newrelic.agent.record_custom_metric('Custom/Audio/NotConnected', 1)
                self.logger.debug(f"[{self._safe_guild_name(guild)}] Voice client not connected for audio playback")
                return

            # Check if the voice client is in a valid state
            if hasattr(guild.voice_client, 'channel') and guild.voice_client.channel is None:
                newrelic.agent.record_custom_metric('Custom/Audio/InvalidState', 1)
                self.logger.debug(f"[{self._safe_guild_name(guild)}] Voice client in invalid state (no channel)")
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
                self.logger.debug(f"[{self._safe_guild_name(guild)}] Audio already playing, skipping")
                return

            # Create audio source and play with better error handling
            try:
                audio_source = discord.FFmpegPCMAudio(audio_path, **FFMPEG_OPTIONS)

                def audio_finished_callback(error):
                    if error:
                        self.logger.error(f'[{self._safe_guild_name(guild)}] Audio player error: {error}')
                        newrelic.agent.record_custom_metric('Custom/Audio/PlaybackError', 1)
                    else:
                        self.logger.debug(f'[{self._safe_guild_name(guild)}] Audio playback completed successfully')

                guild.voice_client.play(audio_source, after=audio_finished_callback)

                safe_guild_name = self._safe_guild_name(guild)
                self.logger.debug(f"[{safe_guild_name}] Playing notification audio: {os.path.basename(audio_path)}")
                newrelic.agent.record_custom_metric('Custom/Audio/PlaybackSuccess', 1)

            except discord.errors.ClientException as e:
                newrelic.agent.record_custom_metric('Custom/Audio/DiscordClientError', 1)
                newrelic.agent.notice_error()
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.error(f"[{safe_guild_name}] Discord client error playing audio: {e}")

                # Try to reconnect if the error suggests connection issues
                if "not connected" in str(e).lower() or "invalid" in str(e).lower():
                    self.logger.info(f"[{safe_guild_name}] Attempting to rejoin voice channel after connection error")
                    await self.join_busiest_channel_if_needed(guild)

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

            safe_guild_name = self._safe_guild_name(guild)

            # If bot is not connected, join the busiest channel
            if not guild.voice_client:
                try:
                    self.logger.debug(f"[{safe_guild_name}] Attempting to join voice channel: {busiest_channel.name}")
                    await busiest_channel.connect(timeout=30.0, reconnect=True)
                    self.logger.info(f"[{safe_guild_name}] Bot joined busiest channel: {busiest_channel.name} ({max_members} members)")
                    newrelic.agent.record_custom_metric('Custom/Voice/ChannelJoin', 1)
                    return
                except asyncio.TimeoutError:
                    self.logger.error(f"[{safe_guild_name}] Timeout joining voice channel: {busiest_channel.name}")
                    newrelic.agent.record_custom_metric('Custom/Voice/JoinTimeout', 1)
                    return
                except discord.ClientException as e:
                    self.logger.error(f"[{safe_guild_name}] Discord client error joining channel {busiest_channel.name}: {e}")
                    newrelic.agent.record_custom_metric('Custom/Voice/JoinError', 1)
                    return

            # Check if voice client is still valid
            if not guild.voice_client.is_connected():
                self.logger.warning(f"[{safe_guild_name}] Voice client exists but not connected, attempting to reconnect")
                try:
                    await guild.voice_client.disconnect(force=True)
                    await asyncio.sleep(1.0)  # Brief pause before reconnecting
                    await busiest_channel.connect(timeout=30.0, reconnect=True)
                    self.logger.info(f"[{safe_guild_name}] Bot reconnected to channel: {busiest_channel.name}")
                    newrelic.agent.record_custom_metric('Custom/Voice/Reconnect', 1)
                    return
                except Exception as reconnect_error:
                    self.logger.error(f"[{safe_guild_name}] Failed to reconnect to voice: {reconnect_error}")
                    newrelic.agent.record_custom_metric('Custom/Voice/ReconnectError', 1)
                    return

            # If bot is connected but not in the busiest channel, move there
            current_channel = guild.voice_client.channel
            if current_channel != busiest_channel:
                try:
                    self.logger.debug(f"[{safe_guild_name}] Moving from {current_channel.name} to {busiest_channel.name}")
                    await guild.voice_client.move_to(busiest_channel)
                    self.logger.info(f"[{safe_guild_name}] Bot moved to busier channel: {busiest_channel.name} ({max_members} members)")
                    newrelic.agent.record_custom_metric('Custom/Voice/ChannelMove', 1)
                except discord.ClientException as e:
                    if "not connected" in str(e).lower():
                        # Connection was lost, try to reconnect instead of move
                        self.logger.warning(f"[{safe_guild_name}] Lost connection during move, reconnecting to {busiest_channel.name}")
                        try:
                            await guild.voice_client.disconnect(force=True)
                            await asyncio.sleep(1.0)
                            await busiest_channel.connect(timeout=30.0, reconnect=True)
                            self.logger.info(f"[{safe_guild_name}] Reconnected to busiest channel: {busiest_channel.name}")
                            newrelic.agent.record_custom_metric('Custom/Voice/MoveReconnect', 1)
                        except Exception as move_reconnect_error:
                            self.logger.error(f"[{safe_guild_name}] Failed to reconnect during move: {move_reconnect_error}")
                            newrelic.agent.record_custom_metric('Custom/Voice/MoveReconnectError', 1)
                    else:
                        self.logger.error(f"[{safe_guild_name}] Error moving to busier channel: {e}")
                        newrelic.agent.record_custom_metric('Custom/Voice/MoveError', 1)

        except discord.ClientException as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Discord client error joining voice channel: {e}")
            newrelic.agent.record_custom_metric('Custom/Voice/GeneralClientError', 1)
        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Unexpected error joining voice channel: {e}")
            newrelic.agent.record_custom_metric('Custom/Voice/GeneralError', 1)
            newrelic.agent.notice_error()

    async def leave_if_empty(self, guild: discord.Guild) -> None:
        """Leave voice channel if no human members are present."""
        try:
            # Check if bot is connected
            if not guild.voice_client:
                self.logger.debug(f"[{self._safe_guild_name(guild)}] No voice client to check for leaving")
                return

            if not guild.voice_client.is_connected():
                self.logger.debug(f"[{self._safe_guild_name(guild)}] Voice client not connected, cleaning up")
                # Clean up the voice client reference if it's not connected
                try:
                    await guild.voice_client.disconnect(force=True)
                except:
                    pass  # Ignore errors during cleanup
                return

            current_channel = guild.voice_client.channel
            if not current_channel:
                self.logger.warning(f"[{self._safe_guild_name(guild)}] Voice client connected but no channel reference")
                try:
                    await guild.voice_client.disconnect(force=True)
                except:
                    pass
                return

            # Add a small delay to ensure discord state is updated
            await asyncio.sleep(0.5)

            human_count = self._count_human_members(current_channel)

            safe_guild_name = self._safe_guild_name(guild)
            self.logger.debug(f"[{safe_guild_name}] Checking if should leave {current_channel.name}: {human_count} human members")

            # Leave if no human members
            if human_count == 0:
                try:
                    await guild.voice_client.disconnect()
                    self.logger.info(f"[{safe_guild_name}] Bot left empty channel: {current_channel.name}")
                    newrelic.agent.record_custom_metric('Custom/Voice/LeftEmpty', 1)
                except discord.ClientException as e:
                    self.logger.warning(f"[{safe_guild_name}] Error disconnecting from empty channel: {e}")
                    # Force disconnect if normal disconnect fails
                    try:
                        await guild.voice_client.disconnect(force=True)
                        self.logger.info(f"[{safe_guild_name}] Force disconnected from channel: {current_channel.name}")
                        newrelic.agent.record_custom_metric('Custom/Voice/ForceDisconnect', 1)
                    except Exception as force_error:
                        self.logger.error(f"[{safe_guild_name}] Failed to force disconnect: {force_error}")
                        newrelic.agent.record_custom_metric('Custom/Voice/DisconnectError', 1)
            else:
                self.logger.debug(f"[{safe_guild_name}] Staying in {current_channel.name} with {human_count} human members")

        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Error checking if should leave empty channel: {e}")
            newrelic.agent.notice_error()

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

        # Initialize TTS manager asynchronously with timeout
        if self.tts_manager:
            try:
                import asyncio

                self.logger.info("Initializing TTS Manager (this may take time on first run)...")

                # Add timeout to prevent blocking Discord connection
                tts_success = await asyncio.wait_for(
                    self.tts_manager.initialize(),
                    timeout=300.0  # 5 minutes timeout
                )

                if tts_success:
                    self.logger.info(f"TTS Manager initialized successfully with provider: {TTS_PROVIDER}")

                    # Log cache statistics
                    if self.tts_manager.cache_manager:
                        cache_stats = self.tts_manager.cache_manager.get_cache_stats()
                        self.logger.info(f"TTS Cache: {cache_stats['current_files']}/{cache_stats['max_files']} files "
                                       f"({cache_stats['usage_percent']}%), {cache_stats['total_size_mb']}MB")
                else:
                    self.logger.warning("TTS Manager initialization failed - TTS functionality disabled")
                    self.logger.warning("Bot will continue without voice announcements")
                    self.tts_manager = None

            except asyncio.TimeoutError:
                self.logger.error("TTS Manager initialization timed out (5 minutes)")
                self.logger.warning("TTS functionality disabled - bot will continue without voice announcements")
                self.tts_manager = None
            except Exception as e:
                self.logger.error(f"Error initializing TTS Manager: {e}")
                self.logger.warning("TTS functionality disabled - bot will continue without voice announcements")
                self.tts_manager = None

        self.logger.info('Monitoring voice channel activity...')

        # Check if bot should join any channels on startup
        await self._check_initial_voice_channels()

        # Start periodic voice connection health check
        self._start_voice_health_check()

    def _start_voice_health_check(self) -> None:
        """Start a background task to periodically check voice connection health."""
        async def voice_health_check():
            while True:
                try:
                    await asyncio.sleep(300)  # Check every 5 minutes

                    for guild in self.guilds:
                        if not self._is_monitoring_guild(guild):
                            continue

                        safe_guild_name = self._safe_guild_name(guild)

                        # Check if voice client exists but is not connected
                        if guild.voice_client and not guild.voice_client.is_connected():
                            self.logger.warning(f"[{safe_guild_name}] Voice client exists but disconnected, cleaning up")
                            try:
                                await guild.voice_client.disconnect(force=True)
                            except:
                                pass

                            # Check if we should rejoin
                            busiest_channel, max_members = await self.find_busiest_voice_channel(guild)
                            if busiest_channel and max_members > 0:
                                self.logger.info(f"[{safe_guild_name}] Attempting to rejoin after health check")
                                try:
                                    await busiest_channel.connect(timeout=30.0, reconnect=True)
                                    self.logger.info(f"[{safe_guild_name}] Rejoined channel: {busiest_channel.name}")
                                    newrelic.agent.record_custom_metric('Custom/Voice/HealthCheckRejoin', 1)
                                except Exception as rejoin_error:
                                    self.logger.error(f"[{safe_guild_name}] Health check rejoin failed: {rejoin_error}")
                                    newrelic.agent.record_custom_metric('Custom/Voice/HealthCheckRejoinError', 1)

                        # Verify we're in the right channel
                        elif guild.voice_client and guild.voice_client.is_connected():
                            current_channel = guild.voice_client.channel
                            busiest_channel, max_members = await self.find_busiest_voice_channel(guild)

                            if current_channel and busiest_channel and current_channel != busiest_channel and max_members > 0:
                                self.logger.debug(f"[{safe_guild_name}] Health check: should move from {current_channel.name} to {busiest_channel.name}")
                                await self.join_busiest_channel_if_needed(guild)

                except Exception as e:
                    self.logger.error(f"Error in voice health check: {e}")
                    newrelic.agent.notice_error()

        # Start the health check task
        asyncio.create_task(voice_health_check())

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
                            self.logger.debug(f"[{safe_guild_name}] Attempting to join channel on startup: {busiest_channel.name}")
                            await busiest_channel.connect(timeout=30.0, reconnect=True)
                            self.logger.info(f"[{safe_guild_name}] Bot joined channel on startup: {busiest_channel.name} ({max_members} members)")
                            newrelic.agent.record_custom_metric('Custom/Bot/StartupChannelJoin', 1)
                        except asyncio.TimeoutError:
                            self.logger.error(f"[{safe_guild_name}] Timeout joining channel on startup: {busiest_channel.name}")
                            newrelic.agent.record_custom_metric('Custom/Bot/StartupJoinTimeout', 1)
                        except discord.ClientException as e:
                            self.logger.error(f"[{safe_guild_name}] Failed to join channel on startup: {e}")
                            newrelic.agent.record_custom_metric('Custom/Bot/StartupChannelJoinError', 1)
                        except Exception as e:
                            self.logger.error(f"[{safe_guild_name}] Unexpected error joining channel on startup: {e}")
                            newrelic.agent.record_custom_metric('Custom/Bot/StartupUnexpectedError', 1)
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

    @newrelic.agent.background_task(name='Discord.on_voice_server_disconnect')
    async def on_voice_server_disconnect(self, channel: discord.VoiceChannel):
        """Called when the bot is disconnected from a voice server."""
        try:
            safe_guild_name = self._safe_guild_name(channel.guild)
            self.logger.warning(f"[{safe_guild_name}] Voice server disconnect from channel: {channel.name}")
            newrelic.agent.record_custom_metric('Custom/Voice/ServerDisconnect', 1)

            # Wait a moment for Discord to stabilize
            await asyncio.sleep(2.0)

            # Check if there are still users in voice channels and attempt to rejoin
            busiest_channel, max_members = await self.find_busiest_voice_channel(channel.guild)
            if busiest_channel and max_members > 0:
                self.logger.info(f"[{safe_guild_name}] Attempting to rejoin after voice server disconnect")
                try:
                    await busiest_channel.connect(timeout=30.0, reconnect=True)
                    self.logger.info(f"[{safe_guild_name}] Successfully rejoined channel: {busiest_channel.name}")
                    newrelic.agent.record_custom_metric('Custom/Voice/AutoRejoin', 1)
                except Exception as rejoin_error:
                    self.logger.error(f"[{safe_guild_name}] Failed to rejoin after disconnect: {rejoin_error}")
                    newrelic.agent.record_custom_metric('Custom/Voice/AutoRejoinError', 1)
            else:
                self.logger.debug(f"[{safe_guild_name}] No active channels to rejoin after disconnect")

        except Exception as e:
            safe_guild_name = self._safe_guild_name(channel.guild) if channel and channel.guild else "Unknown"
            self.logger.error(f"[{safe_guild_name}] Error handling voice server disconnect: {e}")
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
                await self.create_and_play_tts('join', guild, display_name=member.display_name, member_id=member.id)
                await self.join_busiest_channel_if_needed(guild)

            # User left a voice channel
            elif before.channel is not None and after.channel is None:
                newrelic.agent.record_custom_metric('Custom/Discord/UserLeft', 1)
                newrelic.agent.add_custom_attributes({
                    'action': 'left',
                    'channel.name': before.channel.name
                })

                self.logger.info(f"[{safe_guild_name}] {username} left voice channel: {before.channel.name}")
                # Generate TTS audio for user leaving
                await self.create_and_play_tts('leave', guild, display_name=member.display_name, member_id=member.id)
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
                # Generate TTS audio for user moving
                await self.create_and_play_tts('move', guild, display_name=member.display_name, member_id=member.id)
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
