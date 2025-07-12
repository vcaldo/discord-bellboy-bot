import discord
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from typing import Optional, Tuple
from dotenv import load_dotenv

# Initialize New Relic first
import newrelic.agent

# Load environment variables
load_dotenv()

# Initialize New Relic if license key is provided
NEW_RELIC_LICENSE_KEY = os.getenv('NEW_RELIC_LICENSE_KEY')
NEW_RELIC_APP_NAME = os.getenv('NEW_RELIC_APP_NAME', 'Discord-Bellboy-Bot')
NEW_RELIC_ENVIRONMENT = os.getenv('NEW_RELIC_ENVIRONMENT', 'production')

if NEW_RELIC_LICENSE_KEY:
    newrelic.agent.initialize(
        config_file=None,
        environment=NEW_RELIC_ENVIRONMENT,
        license_key=NEW_RELIC_LICENSE_KEY,
        app_name=NEW_RELIC_APP_NAME,
        log_file='/app/logs/newrelic-agent.log',
        log_level='info'
    )
    print(f"New Relic initialized for app: {NEW_RELIC_APP_NAME}")
else:
    print("New Relic license key not found - monitoring disabled")

# Try to import TTS, but make it optional
try:
    from TTS.api import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    TTS = None

# Load environment variables
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
TTS_LANGUAGE = os.getenv('TTS_LANGUAGE', 'en')
TTS_MODEL = os.getenv('TTS_MODEL', f'tts_models/en/ljspeech/fast_pitch')

# Constants
LOGS_DIR = 'logs'
LOG_DATE_FORMAT = '%Y%m%d'
LOG_MESSAGE_FORMAT = '%(asctime)s | %(levelname)s | %(message)s'
TTS_CACHE_SIZE = int(os.getenv('TTS_CACHE_SIZE', '50'))  # Number of TTS files to keep cached

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
        """Initialize Coqui TTS model."""
        # Check if TTS is available
        if not TTS_AVAILABLE:
            self.logger.warning("Coqui TTS not available - TTS functionality will be disabled")
            self.logger.info("Install TTS with: pip install TTS")
            self.tts = None
            self.tts_cache = {}
            return

        try:
            # Initialize TTS with configurable model
            self.logger.info(f"Initializing Coqui TTS with model: {TTS_MODEL}")
            self.tts = TTS(model_name=TTS_MODEL, progress_bar=False)
            self.logger.info("Coqui TTS initialized successfully")

            # Initialize TTS cache tracking
            self.tts_cache = {}  # Dictionary to track cached TTS files

        except Exception as e:
            self.logger.error(f"Failed to initialize Coqui TTS: {e}")
            self.logger.warning("TTS functionality will be disabled")
            self.tts = None
            self.tts_cache = {}

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

    @newrelic.agent.function_trace()
    def create_tts_mp3(self, text: str, output_path: str, speaker: Optional[str] = None) -> bool:
        """
        Create an MP3 file from text using Coqui TTS.

        Args:
            text: The text to convert to speech
            output_path: Path where the MP3 file will be saved
            speaker: Speaker ID or name (if supported by the model)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Record custom metric for TTS requests
            newrelic.agent.record_custom_metric('Custom/TTS/Requests', 1)
            
            # Add custom attributes for better debugging
            newrelic.agent.add_custom_attributes({
                'tts.text_length': len(text),
                'tts.output_path': output_path,
                'tts.speaker': speaker or 'default'
            })

            # Check if TTS is initialized
            if self.tts is None:
                newrelic.agent.record_custom_metric('Custom/TTS/Errors/NotInitialized', 1)
                self.logger.error("Coqui TTS not initialized")
                return False

            # Ensure the output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Create a temporary WAV file first
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            # Generate speech with Coqui TTS
            try:
                with newrelic.agent.FunctionTrace(name='TTS.tts_to_file'):
                    self.tts.tts_to_file(text=text, file_path=temp_wav_path)
            except Exception as e:
                newrelic.agent.record_custom_metric('Custom/TTS/Errors/Generation', 1)
                newrelic.agent.notice_error()
                self.logger.error(f"Coqui TTS generation failed: {e}")
                return False

            # Convert WAV to MP3 using ffmpeg
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file
                '-i', temp_wav_path,
                '-codec:a', 'mp3',
                '-b:a', '128k',
                output_path
            ]

            with newrelic.agent.FunctionTrace(name='FFmpeg.wav_to_mp3'):
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                newrelic.agent.record_custom_metric('Custom/TTS/Errors/FFmpeg', 1)
                self.logger.error(f"ffmpeg conversion failed: {result.stderr}")
                return False

            # Clean up temporary WAV file
            try:
                os.unlink(temp_wav_path)
            except OSError:
                pass

            self.logger.info(f"Coqui TTS MP3 created successfully: {output_path}")

            # Manage TTS cache
            self._manage_tts_cache(output_path)

            # Record successful TTS generation
            newrelic.agent.record_custom_metric('Custom/TTS/Success', 1)
            return True

        except subprocess.TimeoutExpired:
            newrelic.agent.record_custom_metric('Custom/TTS/Errors/Timeout', 1)
            newrelic.agent.notice_error()
            self.logger.error("TTS generation timed out")
            return False
        except Exception as e:
            newrelic.agent.record_custom_metric('Custom/TTS/Errors/General', 1)
            newrelic.agent.notice_error()
            self.logger.error(f"Error creating Coqui TTS MP3: {e}")
            return False

    def _manage_tts_cache(self, new_file_path: str) -> None:
        """
        Manage TTS cache to prevent unlimited growth.

        Args:
            new_file_path: Path to the newly created TTS file
        """
        try:
            # Add new file to cache with current timestamp
            import time
            self.tts_cache[new_file_path] = time.time()

            # If cache size exceeds limit, remove oldest files
            if len(self.tts_cache) > TTS_CACHE_SIZE:
                # Sort by timestamp and remove oldest files
                sorted_cache = sorted(self.tts_cache.items(), key=lambda x: x[1])
                files_to_remove = sorted_cache[:len(self.tts_cache) - TTS_CACHE_SIZE]

                for file_path, _ in files_to_remove:
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        del self.tts_cache[file_path]
                        self.logger.debug(f"Removed old TTS cache file: {file_path}")
                    except OSError as e:
                        self.logger.warning(f"Could not remove TTS cache file {file_path}: {e}")

        except Exception as e:
            self.logger.error(f"Error managing TTS cache: {e}")

    @newrelic.agent.function_trace()
    async def create_and_play_tts(self, text: str, guild: discord.Guild, speaker: Optional[str] = None) -> None:
        """
        Create a TTS MP3 from text using Coqui TTS and play it in the current voice channel.

        Args:
            text: The text to convert to speech and play
            guild: Discord guild where the audio should be played
            speaker: Speaker ID or name (if supported by the model)
        """
        try:
            # Generate a unique filename for the TTS audio
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            tts_filename = f"coqui_tts_{text_hash}.mp3"
            tts_path = f"/app/assets/{tts_filename}"

            # Create the TTS MP3 file using Coqui TTS
            if self.create_tts_mp3(text, tts_path, speaker):
                # Play the generated TTS audio
                await self.play_notification_audio(tts_path, guild)

                # Optional: Clean up the TTS file after a delay to save space
                # You might want to keep frequently used TTS files cached

            else:
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.error(f"[{safe_guild_name}] Failed to create Coqui TTS for: {text}")

        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Error in create_and_play_tts: {e}")

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

    async def on_ready(self):
        """Called when the bot is ready."""
        self.logger.info(f'Bot logged in as {self.user} (ID: {self.user.id})')
        self.logger.info('Monitoring voice channel activity...')

    @newrelic.agent.function_trace()
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
                join_message = f"{member.display_name} entrou"
                tts_audio_path = f"/app/assets/coqui_tts_join_{member.id}.mp3"
                if self.create_tts_mp3(join_message, tts_audio_path):
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
                left_message = f"{member.display_name} saiu"
                tts_audio_path = f"/app/assets/coqui_tts_left_{member.id}.mp3"
                if self.create_tts_mp3(left_message, tts_audio_path):
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
                move_message = f"{member.display_name} moveu"
                tts_audio_path = f"/app/assets/coqui_tts_moved_{member.id}.mp3"
                if self.create_tts_mp3(move_message, tts_audio_path):
                    await self.play_notification_audio(tts_audio_path, guild)
                await self.join_busiest_channel_if_needed(guild)
                await self.leave_if_empty(guild)

        except Exception as e:
            newrelic.agent.record_custom_metric('Custom/Discord/VoiceStateUpdateErrors', 1)
            newrelic.agent.notice_error()
            safe_guild_name = self._safe_guild_name(member.guild)
            self.logger.error(f"[{safe_guild_name}] Error in voice state update: {e}")

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

@newrelic.agent.background_task()
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
