# Audio Assets

## notification.mp3

This file should contain the notification sound that plays when users join, leave, or move between voice channels.

### Recommended Audio Specifications:
- **Format**: MP3 or WAV
- **Duration**: 1-3 seconds (short notification sound)
- **Sample Rate**: 44.1kHz
- **Bitrate**: 128kbps or higher for MP3
- **Channels**: Mono or Stereo

### How to Add Your Audio File:
1. Replace the placeholder `notification.mp3` with your actual audio file
2. Keep the same filename (`notification.mp3`) or update the `AUDIO_FILE_PATH` constant in `bot.py`
3. Test the audio using the `!test_audio` command when the bot is in a voice channel

### FFmpeg Requirement:
Make sure FFmpeg is installed on your system for audio playback to work:
- **Windows**: Download from https://ffmpeg.org/download.html
- **Linux**: `sudo apt install ffmpeg` (Ubuntu/Debian) or equivalent
- **macOS**: `brew install ffmpeg` (with Homebrew)

### Testing:
Use the `!test_audio` command to test if your audio file works correctly.
