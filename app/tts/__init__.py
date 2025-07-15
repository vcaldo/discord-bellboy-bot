"""
TTS module for Discord Bellboy Bot.
Provides text-to-speech functionality with multiple provider support.
"""

from .tts_manager import TTSManager, TTSProvider, CoquiTTSProvider, TTSCacheManager

__all__ = ['TTSManager', 'TTSProvider', 'CoquiTTSProvider', 'TTSCacheManager']
