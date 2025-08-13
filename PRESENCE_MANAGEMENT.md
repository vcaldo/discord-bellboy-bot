# Simplified Presence Management Documentation

## Overview

The presence checking functionality has been **completely reimplemented** with a simplified, cleaner design. The new `PresenceManager` class in `app/presence_manager.py` provides a much easier-to-use and maintain solution for managing bot presence in voice channels.

## 🚀 Key Improvements

### ✅ **Simplified Interface**
- Cleaner method names (`is_human_user` vs `is_human_member`)
- Single method for processing voice updates (`process_voice_update`)
- No Discord.py imports required (works with any objects)

### ✅ **Better Error Handling**
- Uses `getattr()` for safe attribute access
- Handles missing/None attributes gracefully
- More defensive programming throughout

### ✅ **Easier Testing**
- No dependencies on Discord.py for testing
- Mock objects work seamlessly
- Test script runs without Discord connection

### ✅ **All-in-One Processing**
- `process_voice_update()` handles everything in one call
- Returns complete action recommendations
- Eliminates need for multiple decision methods

## 📁 Files

### `app/presence_manager.py`
**New simplified PresenceManager class** with core methods:
- `is_human_user(member)` - Human vs bot detection
- `count_humans_in_channel(channel)` - Channel member counting
- `find_most_active_channel(guild)` - Find busiest channel
- `should_bot_join/move/leave()` - Decision logic
- `get_guild_summary(guild)` - Complete activity overview
- `process_voice_update()` - All-in-one voice event processor

### `app/bellboy.py`
**Updated main bot** with:
- Simplified wrapper methods
- New `handle_voice_update_simplified()` method
- Backward compatibility maintained
- Uses new presence manager interface

### `test_presence.py`
**Comprehensive test suite** that:
- Tests all functionality without Discord connection
- Demonstrates usage patterns
- Provides troubleshooting examples

## 🧠 Core Methods

### **Human Detection**
```python
def is_human_user(self, member) -> bool
```
**Detects**: Bots, webhooks (discriminator "0000"), system users, bot itself

### **Channel Analysis**
```python
def count_humans_in_channel(self, channel) -> int
def find_most_active_channel(self, guild) -> Tuple[channel, count]
```
**Features**: Safe attribute access, respects ignored channels, detailed logging

### **Decision Logic**
```python
def should_bot_join(self, guild, channel, count) -> bool
def should_bot_move(self, guild, channel, count) -> bool
def should_bot_leave(self, guild) -> Tuple[bool, channel]
```
**Logic**: Join if not connected + humans present, move if busier channel exists, leave if current channel empty

### **All-in-One Processor**
```python
def process_voice_update(self, guild, member, before_channel, after_channel) -> dict
```
**Returns**: Complete action recommendation with event type, target channel, reasoning

## 🎯 Usage Examples

### **Basic Usage**
```python
# Initialize
pm = PresenceManager()
pm.set_bot_user_id(bot_id)

# Check if user is human
if pm.is_human_user(member):
    # Process human user activity
    pass

# Get activity overview
summary = pm.get_guild_summary(guild)
print(f"Active channels: {summary['active_channels']}")
```

### **Voice Update Processing**
```python
# Process voice state change (replaces complex event handling)
action = pm.process_voice_update(guild, member, before.channel, after.channel)

# Execute recommended action
if action['action'] == 'join':
    await action['target_channel'].connect()
elif action['action'] == 'move':
    await guild.voice_client.move_to(action['target_channel'])
elif action['action'] == 'leave':
    await guild.voice_client.disconnect()
```

### **Troubleshooting**
```python
# Get detailed guild activity
summary = pm.get_guild_summary(guild)
for channel in summary['channels']:
    print(f"{channel['name']}: {channel['humans']} humans")

# Process update and see reasoning
action = pm.process_voice_update(guild, member, before_ch, after_ch)
print(f"Event: {action['event_type']}, Action: {action['action']}")
print(f"Most active: {action['most_active_channel'].name} ({action['human_count']} humans)")
```

## 🛠️ Integration

### **New Simplified Workflow**
1. **Voice Event**: `on_voice_state_update` triggered
2. **Process**: Single call to `process_voice_update()`
3. **Execute**: Act on returned recommendation
4. **TTS**: Play audio if configured

### **Backward Compatibility**
- Original wrapper methods still work
- Existing bot code unchanged
- Migration to new methods optional

## 📊 Benefits

### **For Development**
- ✅ **No Discord.py dependency** for testing
- ✅ **Cleaner code** with single-purpose methods
- ✅ **Better error handling** with safe attribute access
- ✅ **Comprehensive logging** for debugging

### **For Troubleshooting**
- ✅ **Single method** handles all voice update logic
- ✅ **Detailed action responses** show reasoning
- ✅ **Guild summaries** provide complete overview
- ✅ **Test script** verifies functionality offline

### **For Maintenance**
- ✅ **Simplified logic** easier to understand
- ✅ **Fewer methods** to maintain
- ✅ **Better separation** of concerns
- ✅ **Extensible design** for future features

## 🔧 Configuration

- **`IGNORED_CHANNEL_ID`**: Environment variable to skip specific channels
- **Logging**: Uses `bellboy.presence` logger namespace
- **Bot ID**: Set via `set_bot_user_id()` after initialization

## 🧪 Testing

Run the test suite:
```bash
cd discord-bellboy-bot
python test_presence.py
```

**Tests verify**:
- Human detection logic
- Channel member counting
- Activity summarization
- Decision logic accuracy
- Error handling robustness

## 📈 Migration Guide

### **Current Code** (still works):
```python
if self.presence_manager.is_human_member(member):
    busiest, count = await self.presence_manager.find_busiest_voice_channel(guild)
    if self.presence_manager.should_join_channel(guild, busiest, count):
        await busiest.connect()
```

### **New Simplified Code**:
```python
action = self.presence_manager.process_voice_update(guild, member, before.channel, after.channel)
if action['action'] == 'join':
    await action['target_channel'].connect()
```

The simplified presence manager reduces complexity while improving functionality and maintainability!
