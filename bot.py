import discord
from discord.ext import commands
import logging
import os
from datetime import datetime
from typing import Optional, Tuple, List
from config import config

# Constants
BOT_PREFIX = '!'
LOGS_DIR = 'logs'
LOG_DATE_FORMAT = '%Y%m%d'
LOG_MESSAGE_FORMAT = '%(asctime)s | %(levelname)s | %(message)s'

# Embed colors
EMBED_COLOR_SUCCESS = 0x00ff00
EMBED_COLOR_WARNING = 0xffa500
EMBED_COLOR_ERROR = 0xff0000


class BellboyBot(commands.Bot):
    """
    Discord bot that logs user voice channel activities and manages voice presence.

    Features:
    - Automatically joins the busiest voice channel
    - Leaves empty voice channels
    - Logs voice state changes and member activities
    - Provides voice status commands
    """

    def __init__(self) -> None:
        # Set up intents
        intents = discord.Intents.default()
        intents.voice_states = True  # Required for voice channel events
        intents.members = True       # Required for member events

        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            help_command=None
        )

        # Set up logging
        self._setup_logging()
        self.logger = logging.getLogger('bellboy')

        # Add commands
        self._add_commands()

    def _safe_guild_name(self, guild: discord.Guild) -> str:
        """
        Get a safe representation of guild name for logging.

        Args:
            guild: Discord guild object

        Returns:
            Safe string representation of guild name
        """
        try:
            return guild.name
        except UnicodeEncodeError:
            # Fallback to ASCII-safe representation
            return guild.name.encode('ascii', errors='replace').decode('ascii')
        except Exception:
            return f"Guild_{guild.id}"

    def _format_member_info(self, member: discord.Member) -> str:
        """
        Format member information for logging.

        Args:
            member: Discord member object

        Returns:
            Formatted member information string
        """
        try:
            return f"{member.display_name} ({member.name}#{member.discriminator})"
        except Exception:
            return f"Member_{member.id}"

    def _count_human_members(self, channel: discord.VoiceChannel) -> int:
        """
        Count non-bot members in a voice channel.

        Args:
            channel: Discord voice channel

        Returns:
            Number of human members in the channel
        """
        return len([member for member in channel.members if not member.bot])

    def _is_monitoring_guild(self, guild: discord.Guild) -> bool:
        """
        Check if the bot should monitor this guild.

        Args:
            guild: Discord guild to check

        Returns:
            True if guild should be monitored, False otherwise
        """
        return config.guild_id is None or guild.id == config.guild_id

    def _add_commands(self) -> None:
        """Add bot commands."""

        @self.command(name='join_busiest')
        async def join_busiest_command(ctx: commands.Context) -> None:
            """Manually make the bot join the busiest voice channel."""
            if not self._is_monitoring_guild(ctx.guild):
                return

            await self.join_busiest_channel(ctx.guild)
            await ctx.send("🤖 Checking for busiest voice channel...")

        @self.command(name='leave_voice')
        async def leave_voice_command(ctx: commands.Context) -> None:
            """Make the bot leave the current voice channel."""
            if not self._is_monitoring_guild(ctx.guild):
                return

            if ctx.guild.voice_client:
                await ctx.guild.voice_client.disconnect()
                await ctx.send("👋 Left voice channel!")
                safe_guild_name = self._safe_guild_name(ctx.guild)
                self.logger.info(f"[{safe_guild_name}] Bot manually disconnected from voice channel")
            else:
                await ctx.send("🤷 I'm not in a voice channel!")

        @self.command(name='voice_status')
        async def voice_status_command(ctx: commands.Context) -> None:
            """Show current voice channel status."""
            if not self._is_monitoring_guild(ctx.guild):
                return

            await self._send_voice_status(ctx)

    async def _send_voice_status(self, ctx: commands.Context) -> None:
        """
        Send voice status embed to the context channel.

        Args:
            ctx: Command context
        """
        try:
            busiest_channel, max_members = await self.find_busiest_voice_channel(ctx.guild)

            embed = discord.Embed(title="🎵 Voice Channel Status", color=EMBED_COLOR_SUCCESS)

            # Current channel info
            if ctx.guild.voice_client and ctx.guild.voice_client.is_connected():
                current_channel = ctx.guild.voice_client.channel
                current_members = self._count_human_members(current_channel)
                embed.add_field(
                    name="Current Channel",
                    value=f"{current_channel.name} ({current_members} members)",
                    inline=False
                )
            else:
                embed.add_field(name="Current Channel", value="Not connected", inline=False)

            # Busiest channel info
            if busiest_channel:
                embed.add_field(
                    name="Busiest Channel",
                    value=f"{busiest_channel.name} ({max_members} members)",
                    inline=False
                )
            else:
                embed.add_field(name="Busiest Channel", value="No active channels", inline=False)

            # Configuration status
            embed.add_field(
                name="Auto Join",
                value="✅ Enabled" if config.auto_join_busiest else "❌ Disabled",
                inline=False
            )

            embed.add_field(
                name="Auto Leave Empty",
                value="✅ Enabled" if config.auto_leave_empty else "❌ Disabled",
                inline=False
            )

            await ctx.send(embed=embed)

        except Exception as e:
            safe_guild_name = self._safe_guild_name(ctx.guild)
            self.logger.error(f"[{safe_guild_name}] Error sending voice status: {e}")
            await ctx.send("❌ Error retrieving voice status. Please try again later.")

    def _setup_logging(self) -> None:
        """Set up logging configuration with proper encoding and error handling."""
        try:
            # Create logs directory if it doesn't exist
            if not os.path.exists(LOGS_DIR):
                os.makedirs(LOGS_DIR)

            log_filename = f'{LOGS_DIR}/bellboy_{datetime.now().strftime(LOG_DATE_FORMAT)}.log'

            # Configure logging with UTF-8 encoding to handle Unicode characters
            logging.basicConfig(
                level=getattr(logging, config.log_level),
                format=LOG_MESSAGE_FORMAT,
                handlers=[
                    logging.FileHandler(log_filename, encoding='utf-8'),
                    logging.StreamHandler()
                ]
            )

            # Set encoding for console handler to handle Unicode
            console_handler = logging.getLogger().handlers[-1]
            if hasattr(console_handler, 'stream'):
                try:
                    console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
                except AttributeError:
                    # Fallback for older Python versions
                    pass

        except Exception as e:
            print(f"Warning: Error setting up logging: {e}")
            # Fallback to basic logging
            logging.basicConfig(level=logging.INFO)

    async def on_ready(self) -> None:
        """Called when the bot is ready and connected to Discord."""
        self.logger.info(f'{self.user} has connected to Discord!')
        self.logger.info(f'Bot is in {len(self.guilds)} guilds')

        if config.guild_id:
            guild = self.get_guild(config.guild_id)
            if guild:
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.info(f'Monitoring guild: {safe_guild_name} (ID: {guild.id})')
            else:
                self.logger.warning(f'Could not find guild with ID: {config.guild_id}')
        else:
            self.logger.info('Monitoring all guilds')

    async def find_busiest_voice_channel(self, guild: discord.Guild) -> Tuple[Optional[discord.VoiceChannel], int]:
        """
        Find the voice channel with the most human members.

        Args:
            guild: Discord guild to search in

        Returns:
            Tuple of (busiest_channel, member_count).
            Returns (None, 0) if no channels have members.
        """
        busiest_channel = None
        max_members = 0

        for channel in guild.voice_channels:
            # Count human members in the channel
            member_count = self._count_human_members(channel)

            if member_count > max_members:
                max_members = member_count
                busiest_channel = channel

        return busiest_channel, max_members

    async def join_busiest_channel_on_join(self, guild: discord.Guild) -> None:
        """
        Join the busiest voice channel when someone joins a channel (bot not connected).

        Args:
            guild: Discord guild where the event occurred
        """
        try:
            # Only proceed if bot is not already connected
            if guild.voice_client and guild.voice_client.is_connected():
                return

            # Find the busiest channel
            busiest_channel, max_members = await self.find_busiest_voice_channel(guild)

            # Only join if there are members in the channel
            if busiest_channel and max_members > 0:
                await busiest_channel.connect()
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.info(f"[{safe_guild_name}] Bot joined busiest channel: {busiest_channel.name} ({max_members} members)")

        except discord.ClientException as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Discord client error joining voice channel on user join: {e}")
        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Unexpected error in join_busiest_channel_on_join: {e}")

    async def join_busiest_channel(self, guild: discord.Guild) -> None:
        """
        Join the busiest voice channel in the guild.

        Args:
            guild: Discord guild to find busiest channel in
        """
        try:
            # If bot is already connected, check if we should move
            if guild.voice_client and guild.voice_client.is_connected():
                await self._handle_already_connected(guild)
                return

            # Find the busiest channel
            busiest_channel, max_members = await self.find_busiest_voice_channel(guild)

            # Only join if there are members in the channel
            if busiest_channel and max_members > 0:
                await busiest_channel.connect()
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.info(f"[{safe_guild_name}] Bot joined busiest channel: {busiest_channel.name} ({max_members} members)")
            elif guild.voice_client:
                # If no one is in voice channels, disconnect
                await guild.voice_client.disconnect()
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.info(f"[{safe_guild_name}] Bot disconnected - no members in voice channels")

        except discord.ClientException as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Discord client error joining voice channel: {e}")
        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Unexpected error in join_busiest_channel: {e}")

    async def _handle_already_connected(self, guild: discord.Guild) -> None:
        """
        Handle logic when bot is already connected to a voice channel.

        Args:
            guild: Discord guild where bot is connected
        """
        current_channel = guild.voice_client.channel
        current_members = self._count_human_members(current_channel)

        # Find the busiest channel
        busiest_channel, max_members = await self.find_busiest_voice_channel(guild)

        # If the current channel is still the busiest or tied for busiest, stay
        if not busiest_channel or current_members >= max_members:
            return

        # If there's a busier channel, move to it
        if max_members > current_members:
            await guild.voice_client.move_to(busiest_channel)
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.info(f"[{safe_guild_name}] Bot moved to busier channel: {busiest_channel.name} ({max_members} members)")

    async def check_and_leave_if_empty(self, guild: discord.Guild) -> None:
        """
        Check if the bot's current voice channel is empty and leave if so.

        Args:
            guild: Discord guild to check
        """
        try:
            # Check if bot is connected to a voice channel
            if not guild.voice_client or not guild.voice_client.is_connected():
                return

            current_channel = guild.voice_client.channel

            # Count non-bot members in the channel
            human_members = self._count_human_members(current_channel)

            # If no human members, disconnect
            if human_members == 0:
                await guild.voice_client.disconnect()
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.info(f"[{safe_guild_name}] Bot left voice channel '{current_channel.name}' - no members remaining")

        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Error checking empty channel: {e}")

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        """
        Called when a user's voice state changes.

        Args:
            member: Discord member whose voice state changed
            before: Voice state before the change
            after: Voice state after the change
        """
        # Skip if not monitoring this guild
        if not self._is_monitoring_guild(member.guild):
            return

        username = self._format_member_info(member)
        safe_guild_name = self._safe_guild_name(member.guild)

        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            message = f"[{safe_guild_name}] {username} joined voice channel: {after.channel.name}"
            self.logger.info(message)

            # Only try to join busiest channel when someone joins AND bot isn't already connected
            if config.auto_join_busiest and not member.guild.voice_client:
                await self.join_busiest_channel_on_join(member.guild)

        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            message = f"[{safe_guild_name}] {username} left voice channel: {before.channel.name}"
            self.logger.info(message)

            # Check if bot should leave if the channel became empty
            if config.auto_leave_empty:
                await self.check_and_leave_if_empty(member.guild)

        # User moved between voice channels
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            message = f"[{safe_guild_name}] {username} moved from {before.channel.name} to {after.channel.name}"
            self.logger.info(message)

            # Check if bot should leave if the channel they left became empty
            if config.auto_leave_empty:
                await self.check_and_leave_if_empty(member.guild)

    async def on_member_join(self, member: discord.Member) -> None:
        """
        Called when a member joins the server.

        Args:
            member: Discord member who joined
        """
        # Skip if not monitoring this guild
        if not self._is_monitoring_guild(member.guild):
            return

        username = self._format_member_info(member)
        safe_guild_name = self._safe_guild_name(member.guild)
        message = f"[{safe_guild_name}] {username} joined the server"
        self.logger.info(message)

    async def on_member_remove(self, member: discord.Member) -> None:
        """
        Called when a member leaves the server.

        Args:
            member: Discord member who left
        """
        # Skip if not monitoring this guild
        if not self._is_monitoring_guild(member.guild):
            return

        username = self._format_member_info(member)
        safe_guild_name = self._safe_guild_name(member.guild)
        message = f"[{safe_guild_name}] {username} left the server"
        self.logger.info(message)

    async def on_error(self, event: str, *args, **kwargs) -> None:
        """
        Handle errors that occur during event processing.

        Args:
            event: Name of the event that caused the error
            *args: Positional arguments passed to the event
            **kwargs: Keyword arguments passed to the event
        """
        self.logger.error(f'An error occurred in event {event}', exc_info=True)


def main() -> None:
    """Main function to run the bot."""
    # Validate configuration
    if not config.validate():
        print("Configuration validation failed. Please check your .env file or environment variables.")
        return

    # Create and run the bot
    bot = BellboyBot()

    try:
        bot.run(config.discord_token)
    except discord.LoginFailure:
        print("Error: Invalid Discord token. Please check your DISCORD_TOKEN in .env file.")
    except KeyboardInterrupt:
        print("Bot shutdown requested by user.")
    except Exception as e:
        print(f"Error running bot: {e}")
        logging.getLogger('bellboy').error(f"Fatal error running bot: {e}", exc_info=True)


if __name__ == "__main__":
    main()
