#!/usr/bin/env python3
"""
Fallback TTS system that tries Coqui TTS first, then falls back to espeak
"""

import subprocess
import tempfile
import os
import logging
from typing import Optional

# Try to import TTS
try:
    from TTS.api import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

class FallbackTTS:
    """TTS system that falls back to espeak if Coqui TTS is not available."""

    def __init__(self, logger: logging.Logger, model_name: str = "tts_models/en/ljspeech/fast_pitch"):
        self.logger = logger
        self.model_name = model_name
        self.tts = None
        self.mode = "none"

        self._init_tts()

    def _init_tts(self):
        """Initialize TTS system with fallback."""
        # Try Coqui TTS first
        if TTS_AVAILABLE:
            try:
                self.logger.info(f"Initializing Coqui TTS with model: {self.model_name}")
                self.tts = TTS(model_name=self.model_name, progress_bar=False)
                self.mode = "coqui"
                self.logger.info("Coqui TTS initialized successfully")
                return
            except Exception as e:
                self.logger.warning(f"Coqui TTS initialization failed: {e}")

        # Try espeak as fallback
        try:
            result = subprocess.run(['espeak', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.mode = "espeak"
                self.logger.info("Using espeak for TTS")
                return
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # No TTS available
        self.mode = "none"
        self.logger.warning("No TTS system available - TTS functionality disabled")

    def create_tts_mp3(self, text: str, output_path: str, voice: str = "en", speed: int = 150, pitch: int = 50) -> bool:
        """Create TTS MP3 file using available TTS system."""
        if self.mode == "none":
            self.logger.debug("TTS not available, skipping TTS generation")
            return False

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            if self.mode == "coqui":
                return self._create_coqui_tts(text, output_path)
            elif self.mode == "espeak":
                return self._create_espeak_tts(text, output_path, voice, speed, pitch)

            return False
        except Exception as e:
            self.logger.error(f"Error creating TTS: {e}")
            return False

    def _create_coqui_tts(self, text: str, output_path: str) -> bool:
        """Create TTS using Coqui TTS."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            # Generate speech
            self.tts.tts_to_file(text=text, file_path=temp_wav_path)

            # Convert to MP3
            return self._convert_to_mp3(temp_wav_path, output_path)
        except Exception as e:
            self.logger.error(f"Coqui TTS generation failed: {e}")
            return False

    def _create_espeak_tts(self, text: str, output_path: str, voice: str, speed: int, pitch: int) -> bool:
        """Create TTS using espeak."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            # Generate speech with espeak
            espeak_cmd = [
                'espeak',
                '-v', voice,
                '-s', str(speed),
                '-p', str(pitch),
                '-w', temp_wav_path,
                text
            ]

            result = subprocess.run(espeak_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                self.logger.error(f"espeak failed: {result.stderr}")
                return False

            # Convert to MP3
            return self._convert_to_mp3(temp_wav_path, output_path)
        except Exception as e:
            self.logger.error(f"espeak TTS generation failed: {e}")
            return False

    def _convert_to_mp3(self, wav_path: str, mp3_path: str) -> bool:
        """Convert WAV to MP3 using ffmpeg."""
        try:
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file
                '-i', wav_path,
                '-codec:a', 'mp3',
                '-b:a', '128k',
                mp3_path
            ]

            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)

            # Clean up WAV file
            try:
                os.unlink(wav_path)
            except OSError:
                pass

            if result.returncode != 0:
                self.logger.error(f"ffmpeg conversion failed: {result.stderr}")
                return False

            self.logger.debug(f"TTS MP3 created successfully: {mp3_path}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error("TTS conversion timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error converting to MP3: {e}")
            return False

    def is_available(self) -> bool:
        """Check if any TTS system is available."""
        return self.mode != "none"

    def get_mode(self) -> str:
        """Get the current TTS mode."""
        return self.mode
