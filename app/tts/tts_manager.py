"""
TTS Manager for Discord Bellboy Bot.

This module handles text-to-speech generation using Coqui TTS,
including caching, file management, and New Relic monitoring.
"""

import os
import subprocess
import tempfile
import time
import hashlib
import logging
from typing import Optional, Dict

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

# Try to import TTS, but make it optional
try:
    from TTS.api import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    TTS = None


class TTSManager:
    """
    Manages text-to-speech functionality using Coqui TTS.

    Features:
    - Text-to-speech generation with configurable models
    - File caching to prevent regeneration of identical text
    - FFmpeg integration for audio format conversion
    - New Relic monitoring and metrics
    """

    def __init__(self, logger: logging.Logger):
        """
        Initialize the TTS Manager.

        Args:
            logger: Logger instance for logging TTS operations
        """
        self.logger = logger
        self.tts = None
        self.tts_cache: Dict[str, float] = {}

        # Get configuration from environment
        self.tts_language = os.getenv('TTS_LANGUAGE', 'en')
        self.tts_model = os.getenv('TTS_MODEL', 'tts_models/en/ljspeech/fast_pitch')
        self.cache_size = int(os.getenv('TTS_CACHE_SIZE', '50'))

        # Initialize TTS
        self._init_tts()

    def _init_tts(self) -> None:
        """Initialize Coqui TTS model."""
        # Check if TTS is available
        if not TTS_AVAILABLE:
            self.logger.warning("Coqui TTS not available - TTS functionality will be disabled")
            self.logger.info("Install TTS with: pip install TTS")
            self.tts = None
            self.tts_cache = {}
            return

        try:
            # Initialize TTS with configurable model
            self.logger.info(f"Initializing Coqui TTS with model: {self.tts_model}")
            self.tts = TTS(model_name=self.tts_model, progress_bar=False)
            self.logger.info("Coqui TTS initialized successfully")

            # Initialize TTS cache tracking
            self.tts_cache = {}  # Dictionary to track cached TTS files

        except Exception as e:
            self.logger.error(f"Failed to initialize Coqui TTS: {e}")
            self.logger.warning("TTS functionality will be disabled")
            self.tts = None
            self.tts_cache = {}

    @property
    def is_available(self) -> bool:
        """Check if TTS is available and initialized."""
        return self.tts is not None and TTS_AVAILABLE

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
        tts_filename = f"coqui_{prefix}_{text_hash}.mp3"
        return f"/app/assets/{tts_filename}"

    @newrelic.agent.function_trace()
    def create_tts_mp3(self, text: str, output_path: str, speaker: Optional[str] = None) -> bool:
        """
        Create an MP3 file from text using Coqui TTS.

        Args:
            text: The text to convert to speech
            output_path: Path where the MP3 file will be saved
            speaker: Speaker ID or name (if supported by the model)

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
                'tts.speaker': speaker or 'default'
            })

            # Check if TTS is initialized
            if self.tts is None:
                newrelic.agent.record_custom_metric('Custom/TTS/Errors/NotInitialized', 1)
                self.logger.error("Coqui TTS not initialized")
                return False

            # Check if file already exists (cached)
            if os.path.exists(output_path):
                self.logger.debug(f"TTS file already exists: {output_path}")
                self._manage_tts_cache(output_path)
                newrelic.agent.record_custom_metric('Custom/TTS/CacheHit', 1)
                return True

            # Ensure the output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Create a temporary WAV file first
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            # Generate speech with Coqui TTS
            try:
                with newrelic.agent.FunctionTrace(name='TTS.tts_to_file'):
                    self.tts.tts_to_file(text=text, file_path=temp_wav_path)
            except Exception as e:
                newrelic.agent.record_custom_metric('Custom/TTS/Errors/Generation', 1)
                newrelic.agent.notice_error()
                self.logger.error(f"Coqui TTS generation failed: {e}")
                return False

            # Convert WAV to MP3 using ffmpeg
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file
                '-i', temp_wav_path,
                '-codec:a', 'mp3',
                '-b:a', '128k',
                output_path
            ]

            with newrelic.agent.FunctionTrace(name='FFmpeg.wav_to_mp3'):
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                newrelic.agent.record_custom_metric('Custom/TTS/Errors/FFmpeg', 1)
                self.logger.error(f"ffmpeg conversion failed: {result.stderr}")
                return False

            # Clean up temporary WAV file
            try:
                os.unlink(temp_wav_path)
            except OSError:
                pass

            self.logger.info(f"Coqui TTS MP3 created successfully: {output_path}")

            # Manage TTS cache
            self._manage_tts_cache(output_path)

            # Record successful TTS generation
            newrelic.agent.record_custom_metric('Custom/TTS/Success', 1)
            return True

        except subprocess.TimeoutExpired:
            newrelic.agent.record_custom_metric('Custom/TTS/Errors/Timeout', 1)
            newrelic.agent.notice_error()
            self.logger.error("TTS generation timed out")
            return False
        except Exception as e:
            newrelic.agent.record_custom_metric('Custom/TTS/Errors/General', 1)
            newrelic.agent.notice_error()
            self.logger.error(f"Error creating Coqui TTS MP3: {e}")
            return False

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
        tts_path = f"/app/assets/coqui_tts_join_{user_id}.mp3"

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
        tts_path = f"/app/assets/coqui_tts_left_{user_id}.mp3"

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
        tts_path = f"/app/assets/coqui_tts_moved_{user_id}.mp3"

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

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about the TTS cache.

        Returns:
            Dict with cache statistics
        """
        return {
            'cached_files': len(self.tts_cache),
            'max_cache_size': self.cache_size,
            'available': self.is_available
        }
