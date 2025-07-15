"""
Coqui TTS Provider for Discord Bellboy Bot.

This module implements the Coqui TTS provider using the TTS library.
"""

import os
import subprocess
import tempfile
from typing import Optional, Dict, Any
import logging

from .base_provider import TTSProvider

# Try to import TTS, but make it optional
try:
    from TTS.api import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    TTS = None


class CoquiTTSProvider(TTSProvider):
    """
    Coqui TTS provider implementation.

    Uses the Coqui TTS library for text-to-speech generation.
    """

    def __init__(self, logger: logging.Logger, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Coqui TTS provider.

        Args:
            logger: Logger instance for logging operations
            config: Configuration dictionary for Coqui TTS
        """
        super().__init__(logger, config)
        self.tts = None

        # Set default configuration
        default_config = self.get_default_config()
        self.config = {**default_config, **(config or {})}

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "Coqui TTS"

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for Coqui TTS."""
        return {
            'model': os.getenv('TTS_MODEL', 'tts_models/en/ljspeech/fast_pitch'),
            'language': os.getenv('TTS_LANGUAGE', 'en'),
            'progress_bar': False,
            'gpu': False
        }

    def initialize(self) -> bool:
        """
        Initialize the Coqui TTS provider.

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        if not TTS_AVAILABLE:
            self.logger.warning("Coqui TTS not available - install with: pip install TTS")
            return False

        try:
            model_name = self.config.get('model')
            progress_bar = self.config.get('progress_bar', False)
            gpu = self.config.get('gpu', False)

            self.logger.info(f"Initializing Coqui TTS with model: {model_name}")
            self.tts = TTS(model_name=model_name, progress_bar=progress_bar, gpu=gpu)
            self._initialized = True
            self.logger.info("Coqui TTS initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize Coqui TTS: {e}")
            self.tts = None
            self._initialized = False
            return False

    @property
    def is_available(self) -> bool:
        """Check if Coqui TTS is available and initialized."""
        return TTS_AVAILABLE and self.tts is not None and self._initialized

    def get_supported_formats(self) -> list:
        """Get supported audio formats."""
        return ['wav', 'mp3']

    def generate_speech(self, text: str, output_path: str, **kwargs) -> bool:
        """
        Generate speech using Coqui TTS.

        Args:
            text: The text to convert to speech
            output_path: Path where the audio file will be saved
            **kwargs: Additional parameters (speaker, etc.)

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available:
            self.logger.error("Coqui TTS not initialized")
            return False

        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Get speaker if provided
            speaker = kwargs.get('speaker')

            # Determine output format
            output_format = output_path.split('.')[-1].lower()

            if output_format == 'mp3':
                # Generate to temporary WAV file first, then convert to MP3
                return self._generate_mp3(text, output_path, speaker)
            elif output_format == 'wav':
                # Generate directly to WAV
                return self._generate_wav(text, output_path, speaker)
            else:
                self.logger.error(f"Unsupported output format: {output_format}")
                return False

        except Exception as e:
            self.logger.error(f"Error generating speech with Coqui TTS: {e}")
            return False

    def _generate_wav(self, text: str, output_path: str, speaker: Optional[str] = None) -> bool:
        """Generate WAV file directly."""
        try:
            if speaker:
                self.tts.tts_to_file(text=text, file_path=output_path, speaker=speaker)
            else:
                self.tts.tts_to_file(text=text, file_path=output_path)

            self.logger.info(f"Coqui TTS WAV created: {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"Coqui TTS WAV generation failed: {e}")
            return False

    def _generate_mp3(self, text: str, output_path: str, speaker: Optional[str] = None) -> bool:
        """Generate MP3 file via WAV conversion."""
        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            # Generate WAV first
            if speaker:
                self.tts.tts_to_file(text=text, file_path=temp_wav_path, speaker=speaker)
            else:
                self.tts.tts_to_file(text=text, file_path=temp_wav_path)

            # Convert WAV to MP3 using ffmpeg
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file
                '-i', temp_wav_path,
                '-codec:a', 'mp3',
                '-b:a', '128k',
                output_path
            ]

            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                self.logger.error(f"ffmpeg conversion failed: {result.stderr}")
                return False

            # Clean up temporary WAV file
            try:
                os.unlink(temp_wav_path)
            except OSError:
                pass

            self.logger.info(f"Coqui TTS MP3 created: {output_path}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error("Coqui TTS generation timed out")
            return False
        except Exception as e:
            self.logger.error(f"Coqui TTS MP3 generation failed: {e}")
            return False

    def validate_config(self) -> bool:
        """Validate Coqui TTS configuration."""
        required_keys = ['model']
        for key in required_keys:
            if key not in self.config:
                self.logger.error(f"Missing required config key: {key}")
                return False
        return True

    def cleanup(self) -> None:
        """Clean up Coqui TTS resources."""
        if self.tts:
            del self.tts
            self.tts = None
        self._initialized = False
        self.logger.debug("Coqui TTS provider cleaned up")
