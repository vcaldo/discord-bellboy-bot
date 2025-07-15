"""
TTS Provider Factory for Discord Bellboy Bot.

This module provides a factory for creating TTS provider instances.
"""

import os
import logging
from typing import Optional, Dict, Any, Type

from .base_provider import TTSProvider
from .coqui_provider import CoquiTTSProvider
from .piper_provider import PiperTTSProvider
from .melo_provider import MeloTTSProvider


class TTSProviderFactory:
    """
    Factory class for creating TTS provider instances.
    """

    # Registry of available providers
    _providers = {
        'coqui': CoquiTTSProvider,
        'piper': PiperTTSProvider,
        'melo': MeloTTSProvider,
    }

    @classmethod
    def get_available_providers(cls) -> list:
        """
        Get list of available provider names.

        Returns:
            list: List of available provider names
        """
        return list(cls._providers.keys())

    @classmethod
    def create_provider(cls, provider_name: str, logger: logging.Logger,
                       config: Optional[Dict[str, Any]] = None) -> Optional[TTSProvider]:
        """
        Create a TTS provider instance.

        Args:
            provider_name: Name of the provider to create
            logger: Logger instance
            config: Optional configuration for the provider

        Returns:
            TTSProvider instance or None if provider not found
        """
        provider_name = provider_name.lower()

        if provider_name not in cls._providers:
            logger.error(f"Unknown TTS provider: {provider_name}")
            logger.info(f"Available providers: {cls.get_available_providers()}")
            return None

        try:
            provider_class = cls._providers[provider_name]
            provider = provider_class(logger, config)
            logger.info(f"Created TTS provider: {provider.provider_name}")
            return provider
        except Exception as e:
            logger.error(f"Failed to create TTS provider {provider_name}: {e}")
            return None

    @classmethod
    def create_and_initialize_provider(cls, provider_name: str, logger: logging.Logger,
                                     config: Optional[Dict[str, Any]] = None) -> Optional[TTSProvider]:
        """
        Create and initialize a TTS provider.

        Args:
            provider_name: Name of the provider to create
            logger: Logger instance
            config: Optional configuration for the provider

        Returns:
            Initialized TTSProvider instance or None if failed
        """
        provider = cls.create_provider(provider_name, logger, config)
        if provider is None:
            return None

        if not provider.validate_config():
            logger.error(f"Invalid configuration for provider: {provider_name}")
            return None

        if not provider.initialize():
            logger.error(f"Failed to initialize provider: {provider_name}")
            return None

        return provider

    @classmethod
    def get_default_provider_name(cls) -> str:
        """
        Get the default provider name from environment or fallback.

        Returns:
            str: Default provider name
        """
        return os.getenv('TTS_PROVIDER', 'coqui').lower()

    @classmethod
    def create_default_provider(cls, logger: logging.Logger) -> Optional[TTSProvider]:
        """
        Create the default TTS provider with environment-based configuration.

        Args:
            logger: Logger instance

        Returns:
            Initialized TTSProvider instance or None if failed
        """
        provider_name = cls.get_default_provider_name()
        config = cls._get_provider_config_from_env(provider_name)

        return cls.create_and_initialize_provider(provider_name, logger, config)

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[TTSProvider]) -> None:
        """
        Register a new TTS provider.

        Args:
            name: Name of the provider
            provider_class: Provider class that inherits from TTSProvider
        """
        if not issubclass(provider_class, TTSProvider):
            raise ValueError("Provider class must inherit from TTSProvider")

        cls._providers[name.lower()] = provider_class

    @classmethod
    def _get_provider_config_from_env(cls, provider_name: str) -> Dict[str, Any]:
        """
        Get provider configuration from environment variables.

        Args:
            provider_name: Name of the provider

        Returns:
            Dict containing provider configuration
        """
        config = {}

        if provider_name == 'coqui':
            config = {
                'model': os.getenv('TTS_MODEL', 'tts_models/en/ljspeech/fast_pitch'),
                'language': os.getenv('TTS_LANGUAGE', 'en'),
                'progress_bar': os.getenv('TTS_PROGRESS_BAR', 'false').lower() == 'true',
                'gpu': os.getenv('TTS_GPU', 'false').lower() == 'true'
            }
        elif provider_name == 'piper':
            config = {
                'model_path': os.getenv('PIPER_MODEL_PATH', '/app/models/piper/en_US-lessac-medium.onnx'),
                'speaker_id': int(os.getenv('PIPER_SPEAKER_ID', '0')),
                'length_scale': float(os.getenv('PIPER_LENGTH_SCALE', '1.0')),
                'noise_scale': float(os.getenv('PIPER_NOISE_SCALE', '0.667')),
                'noise_w': float(os.getenv('PIPER_NOISE_W', '0.8')),
                'sample_rate': int(os.getenv('PIPER_SAMPLE_RATE', '22050'))
            }
        elif provider_name == 'melo':
            config = {
                'language': os.getenv('MELO_LANGUAGE', 'EN'),
                'device': os.getenv('MELO_DEVICE', 'auto'),
                'speaker_id': os.getenv('MELO_SPEAKER_ID', 'EN-Default'),
                'speed': float(os.getenv('MELO_SPEED', '1.0')),
                'sample_rate': int(os.getenv('MELO_SAMPLE_RATE', '44100'))
            }

        return config

    @classmethod
    def test_all_providers(cls, logger: logging.Logger) -> Dict[str, bool]:
        """
        Test all available providers to see which ones can be initialized.

        Args:
            logger: Logger instance

        Returns:
            Dict mapping provider names to their availability status
        """
        results = {}

        for provider_name in cls.get_available_providers():
            try:
                provider = cls.create_provider(provider_name, logger)
                if provider:
                    success = provider.initialize()
                    results[provider_name] = success
                    if success:
                        provider.cleanup()
                else:
                    results[provider_name] = False
            except Exception as e:
                logger.error(f"Error testing provider {provider_name}: {e}")
                results[provider_name] = False

        return results
