"""
Simplified Presence Manager for Discord Bellboy Bot

This module provides a clean, simple interface for managing bot presence
in voice channels based on human user activity.
"""

import logging
import os
from typing import Optional, Tuple, List, Dict, Any


class PresenceManager:
    """
    Simple presence manager that handles voice channel monitoring and bot decisions.

    Core responsibilities:
    - Identify human users vs bots
    - Find the most active voice channel
    - Decide when bot should join, move, or leave channels
    """

    def __init__(self):
        """Initialize the presence manager."""
        self.bot_user_id: Optional[int] = None
        self.ignored_channel_id: Optional[str] = os.getenv('IGNORED_CHANNEL_ID')
        self.logger = logging.getLogger('bellboy.presence')

    def set_bot_user_id(self, user_id: int) -> None:
        """Set the bot's user ID for filtering."""
        self.bot_user_id = user_id
        self.logger.debug(f"Bot user ID set to: {user_id}")

    def is_human_user(self, member) -> bool:
        """
        Check if a Discord member is a human user (not bot/webhook/system).

        Args:
            member: Discord member object

        Returns:
            bool: True if member is human
        """
        # Basic bot check
        if getattr(member, 'bot', False):
            return False

        # Don't count the bot itself
        if self.bot_user_id and getattr(member, 'id', None) == self.bot_user_id:
            return False

        # Webhook users have discriminator "0000"
        if getattr(member, 'discriminator', None) == '0000':
            return False

        # System users (if attribute exists)
        if getattr(member, 'system', False):
            return False

        return True

    def count_humans_in_channel(self, channel) -> int:
        """
        Count human members in a voice channel.

        Args:
            channel: Discord voice channel

        Returns:
            int: Number of human members
        """
        if not channel or not hasattr(channel, 'members'):
            return 0

        human_count = sum(1 for member in channel.members if self.is_human_user(member))

        self.logger.debug(f"Channel '{getattr(channel, 'name', 'Unknown')}': {human_count} humans")
        return human_count

    def find_most_active_channel(self, guild) -> Tuple[Optional[Any], int]:
        """
        Find the voice channel with the most human members.

        Args:
            guild: Discord guild

        Returns:
            Tuple of (channel, human_count) or (None, 0) if no active channels
        """
        if not guild or not hasattr(guild, 'voice_channels'):
            return None, 0

        best_channel = None
        max_humans = 0

        for channel in guild.voice_channels:
            # Skip ignored channel
            if self.ignored_channel_id and str(getattr(channel, 'id', '')) == self.ignored_channel_id:
                self.logger.debug(f"Skipping ignored channel: {getattr(channel, 'name', 'Unknown')}")
                continue

            human_count = self.count_humans_in_channel(channel)
            if human_count > max_humans:
                max_humans = human_count
                best_channel = channel

        if best_channel:
            self.logger.debug(f"Most active channel: {getattr(best_channel, 'name', 'Unknown')} ({max_humans} humans)")

        return best_channel, max_humans

    def should_bot_join(self, guild, target_channel, human_count: int) -> bool:
        """
        Determine if bot should join a voice channel.

        Args:
            guild: Discord guild
            target_channel: Channel to potentially join
            human_count: Number of humans in the channel

        Returns:
            bool: True if bot should join
        """
        # No point joining if no humans or no channel
        if not target_channel or human_count == 0:
            return False

        # Join if bot is not connected anywhere
        voice_client = getattr(guild, 'voice_client', None)
        if not voice_client:
            self.logger.debug("Bot should join - not connected anywhere")
            return True

        return False

    def should_bot_move(self, guild, target_channel, human_count: int) -> bool:
        """
        Determine if bot should move to a different channel.

        Args:
            guild: Discord guild
            target_channel: Channel to potentially move to
            human_count: Number of humans in the target channel

        Returns:
            bool: True if bot should move
        """
        # Can't move if no target or no humans
        if not target_channel or human_count == 0:
            return False

        voice_client = getattr(guild, 'voice_client', None)
        if not voice_client:
            return False

        # Move if currently in a different channel
        current_channel = getattr(voice_client, 'channel', None)
        should_move = current_channel and current_channel != target_channel

        if should_move:
            current_name = getattr(current_channel, 'name', 'Unknown')
            target_name = getattr(target_channel, 'name', 'Unknown')
            self.logger.debug(f"Bot should move from '{current_name}' to '{target_name}'")

        return should_move

    def should_bot_leave(self, guild) -> Tuple[bool, Optional[Any]]:
        """
        Determine if bot should leave its current channel.

        Args:
            guild: Discord guild

        Returns:
            Tuple of (should_leave, current_channel)
        """
        voice_client = getattr(guild, 'voice_client', None)
        if not voice_client:
            return False, None

        current_channel = getattr(voice_client, 'channel', None)
        if not current_channel:
            return False, None

        human_count = self.count_humans_in_channel(current_channel)
        should_leave = human_count == 0

        if should_leave:
            self.logger.debug(f"Bot should leave empty channel: {getattr(current_channel, 'name', 'Unknown')}")

        return should_leave, current_channel

    def get_guild_summary(self, guild) -> Dict[str, Any]:
        """
        Get a simple summary of voice activity in the guild.

        Args:
            guild: Discord guild

        Returns:
            dict: Activity summary
        """
        if not guild or not hasattr(guild, 'voice_channels'):
            return {'error': 'Invalid guild'}

        channels = []
        total_humans = 0
        active_channels = 0

        for channel in guild.voice_channels:
            human_count = self.count_humans_in_channel(channel)

            channel_info = {
                'name': getattr(channel, 'name', 'Unknown'),
                'id': str(getattr(channel, 'id', '')),
                'humans': human_count,
                'total_members': len(getattr(channel, 'members', [])),
                'ignored': self.ignored_channel_id and str(getattr(channel, 'id', '')) == self.ignored_channel_id
            }

            channels.append(channel_info)
            total_humans += human_count

            if human_count > 0:
                active_channels += 1

        # Sort by human count (highest first)
        channels.sort(key=lambda x: x['humans'], reverse=True)

        return {
            'guild_name': getattr(guild, 'name', 'Unknown'),
            'total_channels': len(channels),
            'active_channels': active_channels,
            'total_humans': total_humans,
            'channels': channels
        }

    def process_voice_update(self, guild, member, before_channel, after_channel) -> Dict[str, Any]:
        """
        Process a voice state update and return recommended actions.

        Args:
            guild: Discord guild
            member: Member who changed voice state
            before_channel: Channel member was in (or None)
            after_channel: Channel member moved to (or None)

        Returns:
            dict: Recommended actions for the bot
        """
        # Skip if not a human user
        if not self.is_human_user(member):
            return {'action': 'ignore', 'reason': 'Not a human user'}

        # Determine what happened
        if not before_channel and after_channel:
            event_type = 'join'
        elif before_channel and not after_channel:
            event_type = 'leave'
        elif before_channel and after_channel and before_channel != after_channel:
            event_type = 'move'
        else:
            return {'action': 'ignore', 'reason': 'No significant change'}

        # Find the most active channel
        most_active_channel, human_count = self.find_most_active_channel(guild)

        # Determine bot action
        if self.should_bot_join(guild, most_active_channel, human_count):
            action = 'join'
            target = most_active_channel
        elif self.should_bot_move(guild, most_active_channel, human_count):
            action = 'move'
            target = most_active_channel
        elif self.should_bot_leave(guild)[0]:
            action = 'leave'
            target = None
        else:
            action = 'stay'
            target = None

        return {
            'action': action,
            'target_channel': target,
            'event_type': event_type,
            'member_name': getattr(member, 'display_name', 'Unknown'),
            'most_active_channel': most_active_channel,
            'human_count': human_count
        }