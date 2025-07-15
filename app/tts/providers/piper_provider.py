"""
Piper TTS Provider for Discord Bellboy Bot.

This module implements the Piper TTS provider using the piper-tts library.
"""

import os
import subprocess
import tempfile
from typing import Optional, Dict, Any
import logging

from .base_provider import TTSProvider

# Try to import piper-tts, but make it optional
try:
    import piper
    PIPER_AVAILABLE = True
except ImportError:
    PIPER_AVAILABLE = False
    piper = None


class PiperTTSProvider(TTSProvider):
    """
    Piper TTS provider implementation.

    Uses the Piper TTS engine for fast, local text-to-speech generation.
    """

    def __init__(self, logger: logging.Logger, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Piper TTS provider.

        Args:
            logger: Logger instance for logging operations
            config: Configuration dictionary for Piper TTS
        """
        super().__init__(logger, config)
        self.voice = None

        # Set default configuration
        default_config = self.get_default_config()
        self.config = {**default_config, **(config or {})}

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "Piper TTS"

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for Piper TTS."""
        return {
            'model_path': os.getenv('PIPER_MODEL_PATH', '/app/models/piper/en_US-lessac-medium.onnx'),
            'speaker_id': int(os.getenv('PIPER_SPEAKER_ID', '0')),
            'length_scale': float(os.getenv('PIPER_LENGTH_SCALE', '1.0')),
            'noise_scale': float(os.getenv('PIPER_NOISE_SCALE', '0.667')),
            'noise_w': float(os.getenv('PIPER_NOISE_W', '0.8')),
            'sample_rate': int(os.getenv('PIPER_SAMPLE_RATE', '22050'))
        }

    def initialize(self) -> bool:
        """
        Initialize the Piper TTS provider.

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        if not PIPER_AVAILABLE:
            self.logger.warning("Piper TTS not available - install with: pip install piper-tts")
            return False

        try:
            model_path = self.config.get('model_path')

            if not os.path.exists(model_path):
                self.logger.error(f"Piper model not found at: {model_path}")
                return False

            self.logger.info(f"Initializing Piper TTS with model: {model_path}")

            # Load the Piper voice model
            self.voice = piper.PiperVoice.load(model_path)
            self._initialized = True
            self.logger.info("Piper TTS initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize Piper TTS: {e}")
            self.voice = None
            self._initialized = False
            return False

    @property
    def is_available(self) -> bool:
        """Check if Piper TTS is available and initialized."""
        return PIPER_AVAILABLE and self.voice is not None and self._initialized

    def get_supported_formats(self) -> list:
        """Get supported audio formats."""
        return ['wav', 'mp3']

    def generate_speech(self, text: str, output_path: str, **kwargs) -> bool:
        """
        Generate speech using Piper TTS.

        Args:
            text: The text to convert to speech
            output_path: Path where the audio file will be saved
            **kwargs: Additional parameters (speaker_id, length_scale, etc.)

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_available:
            self.logger.error("Piper TTS not initialized")
            return False

        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Get parameters from kwargs or config
            speaker_id = kwargs.get('speaker_id', self.config.get('speaker_id', 0))
            length_scale = kwargs.get('length_scale', self.config.get('length_scale', 1.0))
            noise_scale = kwargs.get('noise_scale', self.config.get('noise_scale', 0.667))
            noise_w = kwargs.get('noise_w', self.config.get('noise_w', 0.8))

            # Determine output format
            output_format = output_path.split('.')[-1].lower()

            if output_format == 'mp3':
                # Generate to temporary WAV file first, then convert to MP3
                return self._generate_mp3(text, output_path, speaker_id, length_scale, noise_scale, noise_w)
            elif output_format == 'wav':
                # Generate directly to WAV
                return self._generate_wav(text, output_path, speaker_id, length_scale, noise_scale, noise_w)
            else:
                self.logger.error(f"Unsupported output format: {output_format}")
                return False

        except Exception as e:
            self.logger.error(f"Error generating speech with Piper TTS: {e}")
            return False

    def _generate_wav(self, text: str, output_path: str, speaker_id: int,
                     length_scale: float, noise_scale: float, noise_w: float) -> bool:
        """Generate WAV file directly."""
        try:
            # Generate speech audio
            audio_data = self.voice.synthesize(
                text,
                speaker_id=speaker_id,
                length_scale=length_scale,
                noise_scale=noise_scale,
                noise_w=noise_w
            )

            # Save audio to WAV file
            with open(output_path, 'wb') as f:
                self.voice.save_wav(audio_data, f)

            self.logger.info(f"Piper TTS WAV created: {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"Piper TTS WAV generation failed: {e}")
            return False

    def _generate_mp3(self, text: str, output_path: str, speaker_id: int,
                     length_scale: float, noise_scale: float, noise_w: float) -> bool:
        """Generate MP3 file via WAV conversion."""
        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            # Generate WAV first
            if not self._generate_wav(text, temp_wav_path, speaker_id, length_scale, noise_scale, noise_w):
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

            self.logger.info(f"Piper TTS MP3 created: {output_path}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error("Piper TTS generation timed out")
            return False
        except Exception as e:
            self.logger.error(f"Piper TTS MP3 generation failed: {e}")
            return False

    def validate_config(self) -> bool:
        """Validate Piper TTS configuration."""
        required_keys = ['model_path']
        for key in required_keys:
            if key not in self.config:
                self.logger.error(f"Missing required config key: {key}")
                return False

        model_path = self.config.get('model_path')
        if not os.path.exists(model_path):
            self.logger.error(f"Piper model file not found: {model_path}")
            return False

        return True

    def cleanup(self) -> None:
        """Clean up Piper TTS resources."""
        if self.voice:
            del self.voice
            self.voice = None
        self._initialized = False
        self.logger.debug("Piper TTS provider cleaned up")
