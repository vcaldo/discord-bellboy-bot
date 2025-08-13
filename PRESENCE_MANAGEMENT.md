# Presence Management Documentation

## Overview

The presence checking functionality has been separated from the main bot code into a dedicated `PresenceManager` class in `app/presence_manager.py`. This separation makes it easier to troubleshoot, test, and maintain presence-related functionality.

## Files

### `app/presence_manager.py`
Contains the `PresenceManager` class with all presence-related logic:
- Human vs bot member detection
- Voice channel member counting
- Finding busiest channels
- Decision logic for joining/leaving channels
- Guild monitoring configuration

### `app/bellboy.py`
The main bot file now uses the `PresenceManager` through delegation:
- Creates a `PresenceManager` instance during initialization
- Wrapper methods delegate to the presence manager
- Maintains backward compatibility with existing code

### `test_presence.py`
Test and demonstration script for the `PresenceManager`:
- Basic functionality tests
- Usage examples
- Troubleshooting guidance

## Key Classes and Methods

### PresenceManager Class

#### Core Methods
- `is_human_member(member)` - Determines if a Discord member is human (not bot/webhook/system)
- `count_human_members(channel)` - Counts human members in a voice channel
- `find_busiest_voice_channel(guild)` - Finds the voice channel with most human members

#### Decision Logic Methods
- `should_join_channel(guild, channel, count)` - Determines if bot should join a channel
- `should_move_to_channel(guild, channel, count)` - Determines if bot should move to a different channel
- `should_leave_channel(guild)` - Determines if bot should leave current channel

#### Monitoring Methods
- `is_monitoring_guild(guild)` - Checks if guild should be monitored
- `get_channel_activity_summary(guild)` - Provides detailed activity report

#### Configuration Methods
- `set_bot_user_id(user_id)` - Sets the bot's user ID for filtering

## Usage Examples

### Basic Usage in Bot Code
```python
# Initialize presence manager
self.presence_manager = PresenceManager()

# Set bot user ID after login
self.presence_manager.set_bot_user_id(self.user.id)

# Check if member is human
if self.presence_manager.is_human_member(member):
    # Handle human member activity
    pass

# Find busiest channel
busiest_channel, count = await self.presence_manager.find_busiest_voice_channel(guild)

# Check if bot should join
if self.presence_manager.should_join_channel(guild, busiest_channel, count):
    await busiest_channel.connect()
```

### Troubleshooting

#### Debug Member Detection Issues
```python
# Check specific member
is_human = self.presence_manager.is_human_member(problematic_member)
print(f"Member {problematic_member.display_name} is human: {is_human}")

# Get detailed activity summary
summary = self.presence_manager.get_channel_activity_summary(guild)
for channel_info in summary['channels']:
    print(f"Channel {channel_info['name']}: {channel_info['human_members']} humans")
```

#### Debug Channel Selection Issues
```python
# Check decision logic
busiest_channel, count = await self.presence_manager.find_busiest_voice_channel(guild)
should_join = self.presence_manager.should_join_channel(guild, busiest_channel, count)
should_move = self.presence_manager.should_move_to_channel(guild, busiest_channel, count)
should_leave, current = self.presence_manager.should_leave_channel(guild)

print(f"Busiest: {busiest_channel.name if busiest_channel else 'None'} ({count} members)")
print(f"Should join: {should_join}")
print(f"Should move: {should_move}")
print(f"Should leave: {should_leave}")
```

## Configuration

### Environment Variables
- `IGNORED_CHANNEL_ID` - Channel ID to ignore when finding busiest channel

### Logging
The `PresenceManager` uses the logger name `bellboy.presence` for its log messages.

## Benefits of Separation

1. **Easier Troubleshooting**: All presence logic is in one place
2. **Better Testing**: Can test presence logic independently of Discord connection
3. **Improved Maintainability**: Clear separation of concerns
4. **Enhanced Debugging**: Dedicated methods for getting activity summaries
5. **Future Extensibility**: Easy to add new presence-related features

## Testing

Run the test script to verify functionality:
```bash
cd discord-bellboy-bot
python test_presence.py
```

## Migration Notes

The refactoring maintains full backward compatibility. Existing bot code continues to work without changes because:
- Original method signatures are preserved
- Methods now delegate to the `PresenceManager`
- No breaking changes to the public API

## Future Enhancements

The separated structure makes it easy to add:
- Guild-specific monitoring rules
- Advanced member filtering options
- Presence analytics and reporting
- Custom decision algorithms
- Integration with external monitoring systems
