import discord
from discord.ext import commands
import logging
from datetime import datetime
from config import config


class BellboyBot(commands.Bot):
    """Discord bot that logs user voice channel activities."""

    def __init__(self):
        # Set up intents
        intents = discord.Intents.default()
        intents.voice_states = True  # Required for voice channel events
        intents.members = True       # Required for member events

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )

        # Set up logging
        self._setup_logging()

        self.logger = logging.getLogger('bellboy')

        # Add commands
        self.add_commands()

    def _safe_guild_name(self, guild):
        """Get a safe representation of guild name for logging."""
        try:
            return guild.name
        except UnicodeEncodeError:
            # Fallback to ASCII-safe representation
            return guild.name.encode('ascii', errors='replace').decode('ascii')
        except Exception:
            return f"Guild_{guild.id}"

    def add_commands(self):
        """Add bot commands."""

        @self.command(name='join_busiest')
        async def join_busiest_command(ctx):
            """Manually make the bot join the busiest voice channel."""
            if config.guild_id and ctx.guild.id != config.guild_id:
                return

            await self.join_busiest_channel(ctx.guild)
            await ctx.send("🤖 Checking for busiest voice channel...")

        @self.command(name='leave_voice')
        async def leave_voice_command(ctx):
            """Make the bot leave the current voice channel."""
            if config.guild_id and ctx.guild.id != config.guild_id:
                return

            if ctx.guild.voice_client:
                await ctx.guild.voice_client.disconnect()
                await ctx.send("👋 Left voice channel!")
                safe_guild_name = self._safe_guild_name(ctx.guild)
                self.logger.info(f"[{safe_guild_name}] Bot manually disconnected from voice channel")
            else:
                await ctx.send("🤷 I'm not in a voice channel!")

        @self.command(name='voice_status')
        async def voice_status_command(ctx):
            """Show current voice channel status."""
            if config.guild_id and ctx.guild.id != config.guild_id:
                return

            busiest_channel, max_members = await self.find_busiest_voice_channel(ctx.guild)

            embed = discord.Embed(title="🎵 Voice Channel Status", color=0x00ff00)

            if ctx.guild.voice_client and ctx.guild.voice_client.is_connected():
                current_channel = ctx.guild.voice_client.channel
                current_members = len([member for member in current_channel.members if not member.bot])
                embed.add_field(
                    name="Current Channel",
                    value=f"{current_channel.name} ({current_members} members)",
                    inline=False
                )
            else:
                embed.add_field(name="Current Channel", value="Not connected", inline=False)

            if busiest_channel:
                embed.add_field(
                    name="Busiest Channel",
                    value=f"{busiest_channel.name} ({max_members} members)",
                    inline=False
                )
            else:
                embed.add_field(name="Busiest Channel", value="No active channels", inline=False)

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

    def _setup_logging(self):
        """Set up logging configuration."""
        # Create logs directory if it doesn't exist
        import os
        if not os.path.exists('logs'):
            os.makedirs('logs')

        # Configure logging with UTF-8 encoding to handle Unicode characters
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format='%(asctime)s | %(levelname)s | %(message)s',
            handlers=[
                logging.FileHandler(
                    f'logs/bellboy_{datetime.now().strftime("%Y%m%d")}.log',
                    encoding='utf-8'
                ),
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

    async def on_ready(self):
        """Called when the bot is ready."""
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

    async def find_busiest_voice_channel(self, guild):
        """Find the voice channel with the most members."""
        busiest_channel = None
        max_members = 0

        for channel in guild.voice_channels:
            # Count members in the channel (excluding bots if desired)
            member_count = len([member for member in channel.members if not member.bot])

            if member_count > max_members:
                max_members = member_count
                busiest_channel = channel

        return busiest_channel, max_members

    async def join_busiest_channel_on_join(self, guild):
        """Join the busiest voice channel when someone joins a channel (bot not connected)."""
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
            self.logger.error(f"[{safe_guild_name}] Error joining voice channel on user join: {e}")
        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Unexpected error in join_busiest_channel_on_join: {e}")

    async def join_busiest_channel(self, guild):
        """Join the busiest voice channel in the guild."""
        try:
            # Skip if the bot is already connected to a voice channel in this guild
            if guild.voice_client and guild.voice_client.is_connected():
                current_channel = guild.voice_client.channel
                current_members = len([member for member in current_channel.members if not member.bot])

                # Find the busiest channel
                busiest_channel, max_members = await self.find_busiest_voice_channel(guild)

                # If the current channel is still the busiest or tied for busiest, stay
                if not busiest_channel or current_members >= max_members:
                    return                # If there's a busier channel, move to it
                if max_members > current_members:
                    await guild.voice_client.move_to(busiest_channel)
                    safe_guild_name = self._safe_guild_name(guild)
                    self.logger.info(f"[{safe_guild_name}] Bot moved to busier channel: {busiest_channel.name} ({max_members} members)")
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
            self.logger.error(f"[{safe_guild_name}] Error joining voice channel: {e}")
        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Unexpected error in join_busiest_channel: {e}")

    async def check_and_leave_if_empty(self, guild):
        """Check if the bot's current voice channel is empty and leave if so."""
        try:
            # Check if bot is connected to a voice channel
            if not guild.voice_client or not guild.voice_client.is_connected():
                return

            current_channel = guild.voice_client.channel

            # Count non-bot members in the channel
            human_members = [member for member in current_channel.members if not member.bot]

            # If no human members, disconnect
            if len(human_members) == 0:
                await guild.voice_client.disconnect()
                safe_guild_name = self._safe_guild_name(guild)
                self.logger.info(f"[{safe_guild_name}] Bot left voice channel '{current_channel.name}' - no members remaining")

        except Exception as e:
            safe_guild_name = self._safe_guild_name(guild)
            self.logger.error(f"[{safe_guild_name}] Error checking empty channel: {e}")

    async def on_voice_state_update(self, member, before, after):
        """Called when a user's voice state changes."""
        # Skip if monitoring specific guild and this isn't it
        if config.guild_id and member.guild.id != config.guild_id:
            return

        username = f"{member.display_name} ({member.name}#{member.discriminator})"
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

    async def on_member_join(self, member):
        """Called when a member joins the server."""
        # Skip if monitoring specific guild and this isn't it
        if config.guild_id and member.guild.id != config.guild_id:
            return

        username = f"{member.display_name} ({member.name}#{member.discriminator})"
        safe_guild_name = self._safe_guild_name(member.guild)
        message = f"[{safe_guild_name}] {username} joined the server"
        self.logger.info(message)

    async def on_member_remove(self, member):
        """Called when a member leaves the server."""
        # Skip if monitoring specific guild and this isn't it
        if config.guild_id and member.guild.id != config.guild_id:
            return

        username = f"{member.display_name} ({member.name}#{member.discriminator})"
        safe_guild_name = self._safe_guild_name(member.guild)
        message = f"[{safe_guild_name}] {username} left the server"
        self.logger.info(message)

    async def on_error(self, event, *args, **kwargs):
        """Handle errors."""
        self.logger.error(f'An error occurred in event {event}', exc_info=True)


def main():
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
    except Exception as e:
        print(f"Error running bot: {e}")


if __name__ == "__main__":
    main()
