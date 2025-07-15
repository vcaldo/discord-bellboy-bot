"""
MeloTTS Provider for Discord Bellboy Bot.

This module implements the MeloTTS provider using the melo library.
"""

import os
import subprocess
import tempfile
from typing import Optional, Dict, Any
import logging

from .base_provider import TTSProvider

# Try to import melo, but make it optional
try:
    from melo.api import TTS as MeloTTS
    MELO_AVAILABLE = True
except ImportError:
    MELO_AVAILABLE = False
    MeloTTS = None


class MeloTTSProvider(TTSProvider):
    """
    MeloTTS provider implementation.

    Uses the MeloTTS library for multilingual text-to-speech generation.
    """

    def __init__(self, logger: logging.Logger, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the MeloTTS provider.

        Args:
            logger: Logger instance for logging operations
            config: Configuration dictionary for MeloTTS
        """
        super().__init__(logger, config)
        self.melo_tts = None

        # Set default configuration
        default_config = self.get_default_config()
        self.config = {**default_config, **(config or {})}

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "MeloTTS"

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for MeloTTS."""
        return {
            'language': os.getenv('MELO_LANGUAGE', 'EN'),
            'device': os.getenv('MELO_DEVICE', 'auto'),
            'speaker_id': os.getenv('MELO_SPEAKER_ID', 'EN-Default'),
            'speed': float(os.getenv('MELO_SPEED', '1.0')),
            'sample_rate': int(os.getenv('MELO_SAMPLE_RATE', '44100'))
        }

    def initialize(self) -> bool:
        """
        Initialize the MeloTTS provider.

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        if not MELO_AVAILABLE:
            self.logger.warning("MeloTTS not available - install with: pip install melo-tts")
            return False

        try:
            language = self.config.get('language', 'EN')
            device = self.config.get('device', 'auto')

            self.logger.info(f"Initializing MeloTTS with language: {language}")

            # Initialize MeloTTS
            self.melo_tts = MeloTTS(language=language, device=device)

            # Download model if needed (this may take some time on first run)
            self.melo_tts.download_model()

            self._initialized = True
            self.logger.info("MeloTTS initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize MeloTTS: {e}")
            self.melo_tts = None
            self._initialized = False
            return False

    @property
    def is_available(self) -> bool:
        """Check if MeloTTS is available and initialized."""
        return MELO_AVAILABLE and self.melo_tts is not None and self._initialized

    def get_supported_formats(self) -> list:
        """Get supported audio formats."""
        return ['wav', 'mp3']

    def generate_speech(self, text: str, output_path: str, **kwargs) -> bool:
        """
        Generate speech using MeloTTS.

        Args:
            text: The text to convert to speech
            output_path: Path where the audio file will be saved
            **kwargs: Additional parameters (speaker_id, speed, etc.)

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available:
            self.logger.error("MeloTTS not initialized")
            return False

        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Get parameters from kwargs or config
            speaker_id = kwargs.get('speaker_id', self.config.get('speaker_id', 'EN-Default'))
            speed = kwargs.get('speed', self.config.get('speed', 1.0))

            # Determine output format
            output_format = output_path.split('.')[-1].lower()

            if output_format == 'mp3':
                # Generate to temporary WAV file first, then convert to MP3
                return self._generate_mp3(text, output_path, speaker_id, speed)
            elif output_format == 'wav':
                # Generate directly to WAV
                return self._generate_wav(text, output_path, speaker_id, speed)
            else:
                self.logger.error(f"Unsupported output format: {output_format}")
                return False

        except Exception as e:
            self.logger.error(f"Error generating speech with MeloTTS: {e}")
            return False

    def _generate_wav(self, text: str, output_path: str, speaker_id: str, speed: float) -> bool:
        """Generate WAV file directly."""
        try:
            # Generate speech
            audio_data = self.melo_tts.tts_to_file(
                text=text,
                speaker_id=speaker_id,
                output_path=output_path,
                speed=speed
            )

            self.logger.info(f"MeloTTS WAV created: {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"MeloTTS WAV generation failed: {e}")
            return False

    def _generate_mp3(self, text: str, output_path: str, speaker_id: str, speed: float) -> bool:
        """Generate MP3 file via WAV conversion."""
        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            # Generate WAV first
            if not self._generate_wav(text, temp_wav_path, speaker_id, speed):
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

            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                self.logger.error(f"ffmpeg conversion failed: {result.stderr}")
                return False

            # Clean up temporary WAV file
            try:
                os.unlink(temp_wav_path)
            except OSError:
                pass

            self.logger.info(f"MeloTTS MP3 created: {output_path}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error("MeloTTS generation timed out")
            return False
        except Exception as e:
            self.logger.error(f"MeloTTS MP3 generation failed: {e}")
            return False

    def get_available_speakers(self) -> list:
        """Get list of available speakers for the current language."""
        if not self.is_available:
            return []

        try:
            return self.melo_tts.get_speakers()
        except Exception as e:
            self.logger.error(f"Error getting MeloTTS speakers: {e}")
            return []

    def validate_config(self) -> bool:
        """Validate MeloTTS configuration."""
        required_keys = ['language']
        for key in required_keys:
            if key not in self.config:
                self.logger.error(f"Missing required config key: {key}")
                return False

        # Validate language
        supported_languages = ['EN', 'ES', 'FR', 'ZH', 'JP', 'KR']
        language = self.config.get('language', 'EN')
        if language not in supported_languages:
            self.logger.error(f"Unsupported language: {language}. Supported: {supported_languages}")
            return False

        return True

    def cleanup(self) -> None:
        """Clean up MeloTTS resources."""
        if self.melo_tts:
            del self.melo_tts
            self.melo_tts = None
        self._initialized = False
        self.logger.debug("MeloTTS provider cleaned up")
