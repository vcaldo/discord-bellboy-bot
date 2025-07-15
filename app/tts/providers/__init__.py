"""
TTS Providers package for Discord Bellboy Bot.

This package contains implementations of various TTS providers
using a common interface.
"""

from .base_provider import TTSProvider
from .coqui_provider import CoquiTTSProvider
from .piper_provider import PiperTTSProvider
from .melo_provider import MeloTTSProvider
from .provider_factory import TTSProviderFactory

__all__ = [
    'TTSProvider',
    'CoquiTTSProvider',
    'PiperTTSProvider',
    'MeloTTSProvider',
    'TTSProviderFactory'
]
