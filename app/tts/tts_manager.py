"""
TTS Manager for Discord Bellboy Bot.

This module handles text-to-speech generation using multiple TTS providers,
including caching, file management, and New Relic monitoring.
"""

import os
import time
import hashlib
import logging
from typing import Optional, Dict

from .providers import TTSProviderFactory, TTSProvider

# Try to import New Relic, but make it optional
try:
    import newrelic.agent
    NEWRELIC_AVAILABLE = True
except ImportError:
    NEWRELIC_AVAILABLE = False
    # Create a mock newrelic module for when it's not available
    class MockNewRelic:
        @staticmethod
        def function_trace():
            def decorator(func):
                return func
            return decorator

        @staticmethod
        def record_custom_metric(name, value):
            pass

        @staticmethod
        def add_custom_attributes(attrs):
            pass

        @staticmethod
        def notice_error():
            pass

        class FunctionTrace:
            def __init__(self, name):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

    newrelic = type('newrelic', (), {'agent': MockNewRelic()})()


class TTSManager:
    """
    Manages text-to-speech functionality using multiple TTS providers.

    Features:
    - Multiple TTS provider support (Coqui, Piper, MeloTTS)
    - Provider switching and fallback
    - File caching to prevent regeneration of identical text
    - New Relic monitoring and metrics
    """

    def __init__(self, logger: logging.Logger, provider_name: Optional[str] = None):
        """
        Initialize the TTS Manager with a specific provider.

        Args:
            logger: Logger instance for logging TTS operations
            provider_name: Name of the TTS provider to use (if None, uses default)
        """
        self.logger = logger
        self.provider: Optional[TTSProvider] = None
        self.tts_cache: Dict[str, float] = {}

        # Get configuration from environment
        self.cache_size = int(os.getenv('TTS_CACHE_SIZE', '50'))
        self.provider_name = provider_name or TTSProviderFactory.get_default_provider_name()

        # Initialize TTS provider
        self._init_provider()

    def _init_provider(self) -> None:
        """Initialize the TTS provider."""
        try:
            self.logger.info(f"Initializing TTS provider: {self.provider_name}")
            self.provider = TTSProviderFactory.create_and_initialize_provider(
                self.provider_name, self.logger
            )

            if self.provider:
                self.logger.info(f"TTS provider '{self.provider.provider_name}' initialized successfully")
            else:
                self.logger.error(f"Failed to initialize TTS provider: {self.provider_name}")
                self._try_fallback_provider()

        except Exception as e:
            self.logger.error(f"Error initializing TTS provider: {e}")
            self._try_fallback_provider()

    def _try_fallback_provider(self) -> None:
        """Try to initialize a fallback provider if the primary one fails."""
        available_providers = TTSProviderFactory.get_available_providers()

        for fallback_name in available_providers:
            if fallback_name != self.provider_name:
                try:
                    self.logger.info(f"Trying fallback TTS provider: {fallback_name}")
                    fallback_provider = TTSProviderFactory.create_and_initialize_provider(
                        fallback_name, self.logger
                    )

                    if fallback_provider:
                        self.provider = fallback_provider
                        self.provider_name = fallback_name
                        self.logger.info(f"Successfully initialized fallback provider: {fallback_name}")
                        return

                except Exception as e:
                    self.logger.warning(f"Fallback provider {fallback_name} also failed: {e}")
                    continue

        self.logger.error("No TTS providers could be initialized")

    @property
    def is_available(self) -> bool:
        """Check if TTS is available and initialized."""
        return self.provider is not None and self.provider.is_available

    def switch_provider(self, provider_name: str) -> bool:
        """
        Switch to a different TTS provider.

        Args:
            provider_name: Name of the new provider to use

        Returns:
            bool: True if switch was successful, False otherwise
        """
        if provider_name == self.provider_name and self.is_available:
            self.logger.info(f"Already using provider: {provider_name}")
            return True

        try:
            # Clean up current provider
            if self.provider:
                self.provider.cleanup()

            # Initialize new provider
            new_provider = TTSProviderFactory.create_and_initialize_provider(
                provider_name, self.logger
            )

            if new_provider:
                self.provider = new_provider
                self.provider_name = provider_name
                self.logger.info(f"Successfully switched to TTS provider: {provider_name}")
                return True
            else:
                self.logger.error(f"Failed to switch to TTS provider: {provider_name}")
                # Try to restore previous provider
                self._init_provider()
                return False

        except Exception as e:
            self.logger.error(f"Error switching TTS provider: {e}")
            return False

    def generate_tts_path(self, text: str, prefix: str = "tts") -> str:
        """
        Generate a consistent file path for TTS audio based on text content.

        Args:
            text: The text to convert to speech
            prefix: Prefix for the filename

        Returns:
            str: Path to the TTS audio file
        """
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        provider_prefix = self.provider_name if self.provider else "unknown"
        tts_filename = f"{provider_prefix}_{prefix}_{text_hash}.mp3"
        return f"/app/assets/{tts_filename}"

    @newrelic.agent.function_trace()
    def create_tts_mp3(self, text: str, output_path: str, **kwargs) -> bool:
        """
        Create an MP3 file from text using the configured TTS provider.

        Args:
            text: The text to convert to speech
            output_path: Path where the MP3 file will be saved
            **kwargs: Additional provider-specific parameters

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Record custom metric for TTS requests
            newrelic.agent.record_custom_metric('Custom/TTS/Requests', 1)

            # Add custom attributes for better debugging
            newrelic.agent.add_custom_attributes({
                'tts.text_length': len(text),
                'tts.output_path': output_path,
                'tts.provider': self.provider_name if self.provider else 'none'
            })

            # Check if TTS provider is available
            if not self.is_available:
                newrelic.agent.record_custom_metric('Custom/TTS/Errors/NotAvailable', 1)
                self.logger.error("No TTS provider available")
                return False

            # Check if file already exists (cached)
            if os.path.exists(output_path):
                self.logger.debug(f"TTS file already exists: {output_path}")
                self._manage_tts_cache(output_path)
                newrelic.agent.record_custom_metric('Custom/TTS/CacheHit', 1)
                return True

            # Ensure the output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Generate speech using the provider
            try:
                with newrelic.agent.FunctionTrace(name=f'TTS.{self.provider_name}.generate_speech'):
                    success = self.provider.generate_speech(text, output_path, **kwargs)
            except Exception as e:
                newrelic.agent.record_custom_metric('Custom/TTS/Errors/Generation', 1)
                newrelic.agent.notice_error()
                self.logger.error(f"TTS generation failed: {e}")
                return False

            if not success:
                newrelic.agent.record_custom_metric('Custom/TTS/Errors/Generation', 1)
                self.logger.error("TTS provider failed to generate speech")
                return False

            self.logger.info(f"TTS MP3 created successfully: {output_path}")

            # Manage TTS cache
            self._manage_tts_cache(output_path)

            # Record successful TTS generation
            newrelic.agent.record_custom_metric('Custom/TTS/Success', 1)
            return True

        except Exception as e:
            newrelic.agent.record_custom_metric('Custom/TTS/Errors/General', 1)
            newrelic.agent.notice_error()
            self.logger.error(f"Error creating TTS MP3: {e}")
            return False

    def get_provider_info(self) -> Dict[str, any]:
        """
        Get information about the current TTS provider.

        Returns:
            Dict containing provider information
        """
        if self.provider:
            return self.provider.get_provider_info()
        else:
            return {
                'name': 'None',
                'available': False,
                'initialized': False,
                'supported_formats': []
            }

    def list_available_providers(self) -> Dict[str, bool]:
        """
        List all available TTS providers and their status.

        Returns:
            Dict mapping provider names to their availability
        """
        return TTSProviderFactory.test_all_providers(self.logger)

    def _manage_tts_cache(self, new_file_path: str) -> None:
        """
        Manage TTS cache to prevent unlimited growth.

        Args:
            new_file_path: Path to the newly created TTS file
        """
        try:
            # Add new file to cache with current timestamp
            self.tts_cache[new_file_path] = time.time()

            # If cache size exceeds limit, remove oldest files
            if len(self.tts_cache) > self.cache_size:
                # Sort by timestamp and remove oldest files
                sorted_cache = sorted(self.tts_cache.items(), key=lambda x: x[1])
                files_to_remove = sorted_cache[:len(self.tts_cache) - self.cache_size]

                for file_path, _ in files_to_remove:
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        del self.tts_cache[file_path]
                        self.logger.debug(f"Removed old TTS cache file: {file_path}")
                    except OSError as e:
                        self.logger.warning(f"Could not remove TTS cache file {file_path}: {e}")

        except Exception as e:
            self.logger.error(f"Error managing TTS cache: {e}")

    def create_user_join_tts(self, display_name: str, user_id: int) -> Optional[str]:
        """
        Create TTS audio for user joining a voice channel.

        Args:
            display_name: Display name of the user
            user_id: Discord user ID

        Returns:
            str: Path to the generated TTS file, or None if failed
        """
        join_message = f"Bem vindo {display_name}"
        provider_prefix = self.provider_name if self.provider else "unknown"
        tts_path = f"/app/assets/{provider_prefix}_tts_join_{user_id}.mp3"

        if self.create_tts_mp3(join_message, tts_path):
            return tts_path
        return None

    def create_user_leave_tts(self, display_name: str, user_id: int) -> Optional[str]:
        """
        Create TTS audio for user leaving a voice channel.

        Args:
            display_name: Display name of the user
            user_id: Discord user ID

        Returns:
            str: Path to the generated TTS file, or None if failed
        """
        leave_message = f"tchau tchau {display_name}"
        provider_prefix = self.provider_name if self.provider else "unknown"
        tts_path = f"/app/assets/{provider_prefix}_tts_left_{user_id}.mp3"

        if self.create_tts_mp3(leave_message, tts_path):
            return tts_path
        return None

    def create_user_move_tts(self, display_name: str, user_id: int) -> Optional[str]:
        """
        Create TTS audio for user moving between voice channels.

        Args:
            display_name: Display name of the user
            user_id: Discord user ID

        Returns:
            str: Path to the generated TTS file, or None if failed
        """
        move_message = f"trocou de canal {display_name}"
        provider_prefix = self.provider_name if self.provider else "unknown"
        tts_path = f"/app/assets/{provider_prefix}_tts_moved_{user_id}.mp3"

        if self.create_tts_mp3(move_message, tts_path):
            return tts_path
        return None

    def cleanup_cache(self) -> None:
        """Clean up all cached TTS files."""
        try:
            for file_path in list(self.tts_cache.keys()):
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    del self.tts_cache[file_path]
                except OSError as e:
                    self.logger.warning(f"Could not remove TTS cache file {file_path}: {e}")

            self.logger.info("TTS cache cleaned up successfully")
        except Exception as e:
            self.logger.error(f"Error cleaning up TTS cache: {e}")

    def cleanup(self) -> None:
        """Clean up all TTS resources."""
        try:
            # Clean up cache
            self.cleanup_cache()

            # Clean up provider
            if self.provider:
                self.provider.cleanup()
                self.provider = None

            self.logger.info("TTS Manager cleaned up successfully")
        except Exception as e:
            self.logger.error(f"Error cleaning up TTS Manager: {e}")

    def get_cache_stats(self) -> Dict[str, any]:
        """
        Get statistics about the TTS cache and provider.

        Returns:
            Dict with cache and provider statistics
        """
        provider_info = self.get_provider_info()

        return {
            'cached_files': len(self.tts_cache),
            'max_cache_size': self.cache_size,
            'current_provider': self.provider_name,
            'provider_available': self.is_available,
            'provider_info': provider_info
        }
