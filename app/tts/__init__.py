"""
Text-to-Speech (TTS) module for the Discord Bellboy Bot.

This module provides TTS functionality using Coqui TTS with caching
and New Relic monitoring integration.
"""

from .tts_manager import TTSManager

__all__ = ['TTSManager']
