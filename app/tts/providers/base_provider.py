"""
Base TTS Provider interface for Discord Bellboy Bot.

This module defines the abstract base class that all TTS providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging


class TTSProvider(ABC):
    """
    Abstract base class for TTS providers.

    All TTS providers must inherit from this class and implement the required methods.
    """

    def __init__(self, logger: logging.Logger, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the TTS provider.

        Args:
            logger: Logger instance for logging operations
            config: Optional configuration dictionary for the provider
        """
        self.logger = logger
        self.config = config or {}
        self._initialized = False

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the TTS provider.

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the TTS provider is available and properly initialized.

        Returns:
            bool: True if provider is available, False otherwise
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Get the name of the TTS provider.

        Returns:
            str: Name of the provider
        """
        pass

    @abstractmethod
    def generate_speech(self, text: str, output_path: str, **kwargs) -> bool:
        """
        Generate speech from text and save to file.

        Args:
            text: The text to convert to speech
            output_path: Path where the audio file will be saved
            **kwargs: Additional provider-specific parameters

        Returns:
            bool: True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_supported_formats(self) -> list:
        """
        Get list of supported audio formats.

        Returns:
            list: List of supported audio formats (e.g., ['wav', 'mp3'])
        """
        pass

    def cleanup(self) -> None:
        """
        Clean up resources used by the provider.

        This method can be overridden by providers if they need specific cleanup.
        """
        pass

    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about the provider.

        Returns:
            Dict containing provider information
        """
        return {
            'name': self.provider_name,
            'available': self.is_available,
            'initialized': self._initialized,
            'supported_formats': self.get_supported_formats()
        }

    def validate_config(self) -> bool:
        """
        Validate the provider configuration.

        Returns:
            bool: True if configuration is valid, False otherwise
        """
        return True

    def get_default_config(self) -> Dict[str, Any]:
        """
        Get default configuration for the provider.

        Returns:
            Dict containing default configuration
        """
        return {}
