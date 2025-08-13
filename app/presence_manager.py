"""
Presence Manager for Discord Bellboy Bot

This module handles all presence checking functionality including:
- Monitoring guild membership
- Counting human members in voice channels
- Finding busiest voice channels
- Managing bot presence in channels based on user activity
"""

import discord
import logging
import os
from typing import Optional, Tuple


class PresenceManager:
    """
    Manages presence checking and channel monitoring for the Discord bot.

    This class handles all logic related to:
    - Determining which guilds to monitor
    - Counting human members vs bots
    - Finding the busiest voice channel
    - Decision logic for joining/leaving channels
    """

    def __init__(self, bot_user_id: Optional[int] = None):
        """
        Initialize the presence manager.

        Args:
            bot_user_id: The bot's user ID for filtering purposes
        """
        self.bot_user_id = bot_user_id
        self.logger = logging.getLogger('bellboy.presence')

        # Get ignored channel ID from environment
        self.ignored_channel_id = os.getenv('IGNORED_CHANNEL_ID')

    def set_bot_user_id(self, bot_user_id: int) -> None:
        """
        Set the bot's user ID after initialization.

        Args:
            bot_user_id: The bot's user ID
        """
        self.bot_user_id = bot_user_id

    def _safe_guild_name(self, guild: discord.Guild) -> str:
        """Get a safe representation of guild name for logging."""
        try:
            return guild.name
        except UnicodeEncodeError:
            return guild.name.encode('ascii', errors='replace').decode('ascii')
        except Exception:
            return f"Guild_{guild.id}"

    def is_monitoring_guild(self, guild: discord.Guild) -> bool:
        """
        Check if the bot should monitor this guild.

        Args:
            guild: Discord guild to check

        Returns:
            bool: True if the guild should be monitored
        """
        # Currently monitors all guilds, but this can be extended
        # to implement guild-specific filtering logic
        return True

    def is_human_member(self, member: discord.Member) -> bool:
        """
        Check if a member is a real human user (not bot, app, or system user).

        Args:
            member: Discord member to check

        Returns:
            bool: True if the member is a human user
        """
        # Skip if it's a bot
        if member.bot:
            return False

        # Skip if it's the bot itself (extra safety check)
        if self.bot_user_id and member.id == self.bot_user_id:
            return False

        # Skip if it's a system user or application (if the attribute exists)
        if hasattr(member, 'system') and member.system:
            return False

        # Skip if it's a webhook user
        if hasattr(member, 'discriminator') and member.discriminator == '0000':
            return False

        return True

    def count_human_members(self, channel: discord.VoiceChannel) -> int:
        """
        Count non-bot members in a voice channel, excluding all bots and applications.

        Args:
            channel: Discord voice channel to count members in

        Returns:
            int: Number of human members in the channel
        """
        if channel is None:
            return 0

        # Filter out bots, applications, and the bot itself
        human_members = [member for member in channel.members if self.is_human_member(member)]

        member_names = [m.display_name for m in human_members]
        self.logger.debug(f"Channel '{channel.name}' has {len(human_members)} human members: {member_names}")
        return len(human_members)

    async def find_busiest_voice_channel(self, guild: discord.Guild) -> Tuple[Optional[discord.VoiceChannel], int]:
        """
        Find the voice channel with the most human members.
        Ignores the channel specified in IGNORED_CHANNEL_ID environment variable.

        Args:
            guild: Discord guild to search in

        Returns:
            Tuple of (busiest_channel, member_count).
            Returns (None, 0) if no channels have members.
        """
        busiest_channel = None
        max_members = 0

        for channel in guild.voice_channels:
            # Skip the ignored channel if it's configured
            if self.ignored_channel_id and str(channel.id) == self.ignored_channel_id:
                self.logger.debug(f"[{self._safe_guild_name(guild)}] Skipping ignored channel: {channel.name} (ID: {channel.id})")
                continue

            member_count = self.count_human_members(channel)
            if member_count > max_members:
                max_members = member_count
                busiest_channel = channel

        return busiest_channel, max_members

    def should_join_channel(self, guild: discord.Guild, busiest_channel: discord.VoiceChannel,
                          max_members: int) -> bool:
        """
        Determine if the bot should join a voice channel.

        Args:
            guild: Discord guild
            busiest_channel: The busiest voice channel found
            max_members: Number of members in the busiest channel

        Returns:
            bool: True if bot should join the channel
        """
        # Only join if there are users in voice channels
        if not busiest_channel or max_members == 0:
            return False

        # If bot is not connected, should join the busiest channel
        if not guild.voice_client:
            return True

        return False

    def should_move_to_channel(self, guild: discord.Guild, busiest_channel: discord.VoiceChannel,
                             max_members: int) -> bool:
        """
        Determine if the bot should move to a different voice channel.

        Args:
            guild: Discord guild
            busiest_channel: The busiest voice channel found
            max_members: Number of members in the busiest channel

        Returns:
            bool: True if bot should move to the channel
        """
        # Only consider moving if there are users and bot is connected
        if not busiest_channel or max_members == 0 or not guild.voice_client:
            return False

        # If bot is connected but not in the busiest channel, should move there
        current_channel = guild.voice_client.channel
        return current_channel != busiest_channel

    def should_leave_channel(self, guild: discord.Guild) -> Tuple[bool, Optional[discord.VoiceChannel]]:
        """
        Determine if the bot should leave its current voice channel.

        Args:
            guild: Discord guild

        Returns:
            Tuple of (should_leave, current_channel)
        """
        # Check if bot is connected
        if not guild.voice_client or not guild.voice_client.is_connected():
            self.logger.debug(f"[{self._safe_guild_name(guild)}] Bot not connected to any voice channel")
            return False, None

        current_channel = guild.voice_client.channel
        human_count = self.count_human_members(current_channel)

        safe_guild_name = self._safe_guild_name(guild)
        self.logger.debug(f"[{safe_guild_name}] Checking if should leave {current_channel.name}: {human_count} human members")

        # Leave if no human members
        should_leave = human_count == 0

        if not should_leave:
            self.logger.debug(f"[{safe_guild_name}] Staying in {current_channel.name} with {human_count} human members")

        return should_leave, current_channel

    def get_channel_activity_summary(self, guild: discord.Guild) -> dict:
        """
        Get a summary of voice channel activity in the guild.

        Args:
            guild: Discord guild to analyze

        Returns:
            dict: Summary of channel activity including member counts
        """
        summary = {
            'total_channels': len(guild.voice_channels),
            'active_channels': 0,
            'total_human_members': 0,
            'channels': []
        }

        for channel in guild.voice_channels:
            human_count = self.count_human_members(channel)

            channel_info = {
                'name': channel.name,
                'id': channel.id,
                'human_members': human_count,
                'total_members': len(channel.members),
                'is_ignored': self.ignored_channel_id and str(channel.id) == self.ignored_channel_id
            }

            summary['channels'].append(channel_info)

            if human_count > 0:
                summary['active_channels'] += 1
                summary['total_human_members'] += human_count

        # Sort channels by human member count (descending)
        summary['channels'].sort(key=lambda x: x['human_members'], reverse=True)

        return summary
