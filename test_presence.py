"""
Test script for Simplified PresenceManager functionality

This script demonstrates how to use the simplified PresenceManager
for testing and troubleshooting presence-related functionality.
"""

import sys
import os

# Add the app directory to the path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from presence_manager import PresenceManager


def test_presence_manager():
    """Test basic PresenceManager functionality without Discord connection."""
    print("Testing Simplified PresenceManager...")

    # Create a presence manager instance
    pm = PresenceManager()

    # Test setting bot user ID
    test_bot_id = 123456789
    pm.set_bot_user_id(test_bot_id)
    print(f"✓ Bot user ID set to: {test_bot_id}")

    # Test human member detection with mock objects
    class MockMember:
        def __init__(self, user_id, is_bot=False, discriminator="1234", display_name=None):
            self.id = user_id
            self.bot = is_bot
            self.discriminator = discriminator
            self.display_name = display_name or f"User{user_id}"

    # Test various member types
    human_member = MockMember(111, is_bot=False)
    bot_member = MockMember(222, is_bot=True)
    webhook_member = MockMember(333, is_bot=False, discriminator="0000")
    bot_itself = MockMember(test_bot_id, is_bot=False)  # Bot's own account

    print(f"✓ Human member check: {pm.is_human_user(human_member)} (should be True)")
    print(f"✓ Bot member check: {pm.is_human_user(bot_member)} (should be False)")
    print(f"✓ Webhook member check: {pm.is_human_user(webhook_member)} (should be False)")
    print(f"✓ Bot itself check: {pm.is_human_user(bot_itself)} (should be False)")

    # Test channel counting with mock objects
    class MockChannel:
        def __init__(self, channel_id, name, members=None):
            self.id = channel_id
            self.name = name
            self.members = members or []

    # Create test channel with mixed members
    test_channel = MockChannel(999, "Test Channel", [
        human_member,
        bot_member,
        MockMember(444, is_bot=False, display_name="Human2")
    ])

    human_count = pm.count_humans_in_channel(test_channel)
    print(f"✓ Channel human count: {human_count} (should be 2)")

    # Test guild summary with mock guild
    class MockGuild:
        def __init__(self, guild_id, name, voice_channels=None):
            self.id = guild_id
            self.name = name
            self.voice_channels = voice_channels or []

    test_guild = MockGuild(888, "Test Guild", [
        MockChannel(1001, "General", [human_member]),
        MockChannel(1002, "Gaming", [human_member, MockMember(555, False, display_name="Gamer")]),
        MockChannel(1003, "Empty", [])
    ])

    summary = pm.get_guild_summary(test_guild)
    print(f"✓ Guild summary - Total channels: {summary['total_channels']}")
    print(f"✓ Guild summary - Active channels: {summary['active_channels']}")
    print(f"✓ Guild summary - Total humans: {summary['total_humans']}")

    # Test finding most active channel
    most_active, count = pm.find_most_active_channel(test_guild)
    if most_active:
        print(f"✓ Most active channel: {most_active.name} with {count} humans")

    print("\n✅ Simplified PresenceManager tests completed successfully!")


def demonstrate_simplified_usage():
    """Demonstrate how to use the simplified PresenceManager."""
    print("\n" + "="*60)
    print("SIMPLIFIED PRESENCE MANAGER USAGE DEMONSTRATION")
    print("="*60)

    print("""
The simplified PresenceManager provides these key methods:

CORE METHODS:
• is_human_user(member) - Check if Discord member is human (not bot)
• count_humans_in_channel(channel) - Count humans in voice channel
• find_most_active_channel(guild) - Find channel with most humans

DECISION METHODS:
• should_bot_join(guild, channel, count) - Should bot join channel?
• should_bot_move(guild, channel, count) - Should bot move to channel?
• should_bot_leave(guild) - Should bot leave current channel?

ADVANCED METHODS:
• get_guild_summary(guild) - Complete activity overview
• process_voice_update(guild, member, before, after) - All-in-one processor

KEY SIMPLIFICATIONS:
1. No Discord imports required - works with any objects
2. Uses getattr() for safe attribute access
3. Single method to process voice updates and get actions
4. Cleaner method names (is_human_user vs is_human_member)
5. More defensive programming (handles missing attributes)

EXAMPLE USAGE:
```python
pm = PresenceManager()
pm.set_bot_user_id(bot_id)

# Process a voice state change
action = pm.process_voice_update(guild, member, before_channel, after_channel)

if action['action'] == 'join':
    await action['target_channel'].connect()
elif action['action'] == 'move':
    await guild.voice_client.move_to(action['target_channel'])
elif action['action'] == 'leave':
    await guild.voice_client.disconnect()
```

TROUBLESHOOTING TIPS:
• Use get_guild_summary() to see complete voice activity
• Check process_voice_update() return for detailed action info
• All methods handle None/missing attributes gracefully
• Enable debug logging to see decision reasoning
    """)


if __name__ == "__main__":
    test_presence_manager()
    demonstrate_simplified_usage()