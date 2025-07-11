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

    def _setup_logging(self):
        """Set up logging configuration."""
        # Create logs directory if it doesn't exist
        import os
        if not os.path.exists('logs'):
            os.makedirs('logs')

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format='%(asctime)s | %(levelname)s | %(message)s',
            handlers=[
                logging.FileHandler(f'logs/bellboy_{datetime.now().strftime("%Y%m%d")}.log'),
                logging.StreamHandler()
            ]
        )

    async def on_ready(self):
        """Called when the bot is ready."""
        self.logger.info(f'{self.user} has connected to Discord!')
        self.logger.info(f'Bot is in {len(self.guilds)} guilds')

        if config.guild_id:
            guild = self.get_guild(config.guild_id)
            if guild:
                self.logger.info(f'Monitoring guild: {guild.name} (ID: {guild.id})')
            else:
                self.logger.warning(f'Could not find guild with ID: {config.guild_id}')
        else:
            self.logger.info('Monitoring all guilds')

    async def on_voice_state_update(self, member, before, after):
        """Called when a user's voice state changes."""
        # Skip if monitoring specific guild and this isn't it
        if config.guild_id and member.guild.id != config.guild_id:
            return

        username = f"{member.display_name} ({member.name}#{member.discriminator})"
        guild_name = member.guild.name

        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            message = f"[{guild_name}] {username} joined voice channel: {after.channel.name}"
            self.logger.info(message)

        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            message = f"[{guild_name}] {username} left voice channel: {before.channel.name}"
            self.logger.info(message)

        # User moved between voice channels
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            message = f"[{guild_name}] {username} moved from {before.channel.name} to {after.channel.name}"
            self.logger.info(message)

    async def on_member_join(self, member):
        """Called when a member joins the server."""
        # Skip if monitoring specific guild and this isn't it
        if config.guild_id and member.guild.id != config.guild_id:
            return

        username = f"{member.display_name} ({member.name}#{member.discriminator})"
        guild_name = member.guild.name
        message = f"[{guild_name}] {username} joined the server"
        self.logger.info(message)

    async def on_member_remove(self, member):
        """Called when a member leaves the server."""
        # Skip if monitoring specific guild and this isn't it
        if config.guild_id and member.guild.id != config.guild_id:
            return

        username = f"{member.display_name} ({member.name}#{member.discriminator})"
        guild_name = member.guild.name
        message = f"[{guild_name}] {username} left the server"
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
