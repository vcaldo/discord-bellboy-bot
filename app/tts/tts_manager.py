"""
TTS Manager module for handling multiple TTS providers.
"""
import os
import yaml
import logging
import tempfile
import subprocess
import hashlib
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pathlib import Path

# Import TTS libraries with fallback
try:
    from TTS.api import TTS
    COQUI_AVAILABLE = True
except ImportError:
    COQUI_AVAILABLE = False
    TTS = None


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    def __init__(self, config: Dict[str, Any], cache_manager: 'TTSCacheManager'):
        self.config = config
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(f'bellboy.tts.{self.provider_name}')
        self.is_initialized = False

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the TTS provider. Return True if successful."""
        pass

    @abstractmethod
    async def synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        """Synthesize text to audio file. Return True if successful."""
        pass

    def get_message(self, message_type: str, **kwargs) -> str:
        """Get a formatted message for the given type."""
        messages = self.config.get('messages', {})
        template = messages.get(message_type, f"{message_type} {{display_name}}")
        return template.format(**kwargs)


class CoquiTTSProvider(TTSProvider):
    """Coqui TTS provider implementation."""

    @property
    def provider_name(self) -> str:
        return "coqui"

    def __init__(self, config: Dict[str, Any], cache_manager: 'TTSCacheManager'):
        super().__init__(config, cache_manager)
        self.tts = None

    async def initialize(self) -> bool:
        """Initialize Coqui TTS."""
        if not COQUI_AVAILABLE:
            self.logger.warning("Coqui TTS not available - install with: pip install TTS")
            return False

        try:
            import asyncio

            model = self.config.get('model', 'tts_models/en/ljspeech/tacotron2-DDC')
            settings = self.config.get('settings', {})
            progress_bar = settings.get('progress_bar', False)

            self.logger.info(f"Initializing Coqui TTS with model: {model}")
            self.logger.info("This may take a few minutes on first run (downloading model)...")

            def init_tts():
                """Initialize TTS in a separate thread."""
                try:
                    return TTS(model_name=model, progress_bar=progress_bar)
                except Exception as e:
                    self.logger.error(f"TTS initialization failed: {e}")
                    if "github" in str(e).lower() or "download" in str(e).lower():
                        self.logger.error("Model download failed. This could be due to:")
                        self.logger.error("- Network connectivity issues")
                        self.logger.error("- GitHub rate limiting")
                        self.logger.error("- Invalid model name")
                        self.logger.error("Try again later or use a different model.")
                    raise

            # Run TTS initialization in a thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            self.tts = await loop.run_in_executor(None, init_tts)

            self.is_initialized = True
            self.logger.info("Coqui TTS initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize Coqui TTS: {e}")
            self.logger.error("TTS will be disabled. Bot will continue without voice announcements.")
            return False

    async def synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        """Synthesize text using Coqui TTS."""
        if not self.is_initialized or self.tts is None:
            self.logger.error("Coqui TTS not initialized")
            return False

        try:
            import asyncio

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            # Log synthesis start
            self.logger.debug(f"Starting Coqui TTS synthesis for text length: {len(text)} characters")

            # Generate speech in thread to avoid blocking event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.tts.tts_to_file(text=text, file_path=temp_wav_path)
            )

            self.logger.debug(f"Coqui TTS synthesis completed, converting to {output_path.split('.')[-1].upper()}")

            # Convert to MP3 if needed
            if output_path.endswith('.mp3'):
                return await self._convert_to_mp3(temp_wav_path, output_path)
            else:
                # Just rename/move the WAV file
                os.rename(temp_wav_path, output_path)
                self.logger.debug(f"WAV file saved: {os.path.basename(output_path)}")
                return True

        except Exception as e:
            self.logger.error(f"Coqui TTS synthesis failed: {e}")
            return False

    async def _convert_to_mp3(self, wav_path: str, mp3_path: str) -> bool:
        """Convert WAV to MP3 using ffmpeg."""
        try:
            import asyncio

            settings = self.config.get('settings', {})
            audio_quality = settings.get('audio_quality', '128k')

            ffmpeg_cmd = [
                'ffmpeg', '-y',  # Overwrite output
                '-i', wav_path,
                '-codec:a', 'mp3',
                '-b:a', audio_quality,
                mp3_path
            ]

            # Run ffmpeg in thread to avoid blocking event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)
            )

            # Clean up temporary WAV file
            try:
                os.unlink(wav_path)
            except OSError:
                pass

            if result.returncode == 0:
                self.logger.debug(f"Successfully converted to MP3: {mp3_path}")
                return True
            else:
                self.logger.error(f"ffmpeg conversion failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.logger.error("ffmpeg conversion timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error converting to MP3: {e}")
            return False


class TTSCacheManager:
    """Manages TTS file caching."""

    def __init__(self, cache_config: Dict[str, Any]):
        self.config = cache_config
        self.cache = {}  # filepath -> timestamp
        self.logger = logging.getLogger('bellboy.tts.cache')

        # Ensure cache directory exists
        cache_dir = self.config.get('directory', '/app/assets')
        os.makedirs(cache_dir, exist_ok=True)

        # Log cache configuration
        max_files = self.config.get('max_files', 50)
        enabled = self.config.get('enabled', True)
        self.logger.info(f"TTS Cache initialized: enabled={enabled}, max_files={max_files}, directory={cache_dir}")

        # Load existing cache files if any
        self._scan_existing_cache()

    def add_file(self, file_path: str) -> None:
        """Add a file to the cache tracking."""
        if not self.config.get('enabled', True):
            return

        self.cache[file_path] = time.time()
        self.logger.debug(f"Added file to cache: {os.path.basename(file_path)} (total cached: {len(self.cache)})")
        self._cleanup_if_needed()

    def invalidate_file(self, file_path: str) -> bool:
        """Remove a file from cache and filesystem."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.debug(f"Invalidated cache file: {os.path.basename(file_path)}")

            if file_path in self.cache:
                del self.cache[file_path]

            return True
        except OSError as e:
            self.logger.warning(f"Could not invalidate cache file {os.path.basename(file_path)}: {e}")
            return False

    def _cleanup_if_needed(self) -> None:
        """Clean up old cache files if limit exceeded."""
        max_files = self.config.get('max_files', 50)

        if len(self.cache) <= max_files:
            return

        # Sort by timestamp and remove oldest files
        sorted_cache = sorted(self.cache.items(), key=lambda x: x[1])
        files_to_remove = sorted_cache[:len(self.cache) - max_files]

        self.logger.info(f"Cache limit exceeded ({len(self.cache)}/{max_files}), cleaning up {len(files_to_remove)} old files")

        for file_path, _ in files_to_remove:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.cache[file_path]
                self.logger.debug(f"Removed old cache file: {os.path.basename(file_path)}")
            except OSError as e:
                self.logger.warning(f"Could not remove cache file {os.path.basename(file_path)}: {e}")

        self.logger.info(f"Cache cleanup completed. Current cache size: {len(self.cache)}/{max_files}")

    def _scan_existing_cache(self) -> None:
        """Scan cache directory for existing files and add them to tracking."""
        if not self.config.get('enabled', True):
            return

        cache_dir = self.config.get('directory', '/app/assets')
        try:
            if os.path.exists(cache_dir):
                # Look for TTS files (mp3, wav)
                import glob
                patterns = ['*.mp3', '*.wav']
                existing_files = []

                for pattern in patterns:
                    existing_files.extend(glob.glob(os.path.join(cache_dir, pattern)))

                # Add existing files to cache with current timestamp
                current_time = time.time()
                for file_path in existing_files:
                    if os.path.isfile(file_path):
                        # Use file modification time if available, otherwise current time
                        try:
                            file_time = os.path.getmtime(file_path)
                        except OSError:
                            file_time = current_time
                        self.cache[file_path] = file_time

                if existing_files:
                    self.logger.info(f"Found {len(existing_files)} existing TTS files in cache")
                else:
                    self.logger.debug("No existing TTS files found in cache directory")

        except Exception as e:
            self.logger.warning(f"Error scanning existing cache files: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        cache_dir = self.config.get('directory', '/app/assets')
        max_files = self.config.get('max_files', 50)

        stats = {
            'enabled': self.config.get('enabled', True),
            'directory': cache_dir,
            'max_files': max_files,
            'current_files': len(self.cache),
            'usage_percent': round((len(self.cache) / max_files) * 100, 1) if max_files > 0 else 0
        }

        # Calculate total cache size
        total_size = 0
        for file_path in self.cache.keys():
            try:
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
            except OSError:
                pass

        stats['total_size_mb'] = round(total_size / (1024 * 1024), 2)
        return stats


class TTSManager:
    """Main TTS manager that handles multiple providers."""

    def __init__(self, config_path: str = "tts-config.yaml", provider_name: Optional[str] = None):
        self.logger = logging.getLogger('bellboy.tts')
        self.config = self._load_config(config_path)
        self.cache_manager = TTSCacheManager(self.config.get('cache', {}))

        # Determine provider
        self.provider_name = provider_name or os.getenv('TTS_PROVIDER') or self.config.get('default_provider', 'coqui')
        self.provider = None

        # Provider registry
        self.providers = {
            'coqui': CoquiTTSProvider
        }

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load TTS configuration from YAML file."""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                self.logger.warning(f"Config file not found: {config_path}, using defaults")
                return self._get_default_config()

            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.logger.info(f"Loaded TTS config from: {config_path}")
                return config

        except Exception as e:
            self.logger.error(f"Error loading TTS config: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if file loading fails."""
        return {
            'providers': {
                'coqui': {
                    'name': 'Coqui TTS',
                    'enabled': True,
                    'model': 'tts_models/en/ljspeech/tacotron2-DDC',  # Faster model for quick init
                    'settings': {
                        'progress_bar': False,
                        'output_format': 'mp3',
                        'audio_quality': '128k'
                    },
                    'messages': {
                        'join': 'Welcome {display_name}',
                        'leave': 'Bye bye {display_name}',
                        'move': 'Moved channels {display_name}'
                    }
                }
            },
            'default_provider': 'coqui',
            'cache': {
                'enabled': True,
                'max_files': 50,
                'directory': '/app/assets'
            }
        }

    async def initialize(self) -> bool:
        """Initialize the TTS manager and selected provider."""
        try:
            # Check if provider exists in config
            providers_config = self.config.get('providers', {})
            if self.provider_name not in providers_config:
                self.logger.error(f"Provider '{self.provider_name}' not found in config")
                return False

            provider_config = providers_config[self.provider_name]

            # Check if provider is enabled
            if not provider_config.get('enabled', False):
                self.logger.error(f"Provider '{self.provider_name}' is disabled")
                return False

            # Check if provider class exists
            if self.provider_name not in self.providers:
                self.logger.error(f"Provider class for '{self.provider_name}' not implemented")
                return False

            # Initialize provider
            provider_class = self.providers[self.provider_name]
            self.provider = provider_class(provider_config, self.cache_manager)

            success = await self.provider.initialize()
            if success:
                self.logger.info(f"TTS Manager initialized with provider: {self.provider_name}")
            else:
                self.logger.error(f"Failed to initialize provider: {self.provider_name}")

            return success

        except Exception as e:
            self.logger.error(f"Error initializing TTS Manager: {e}")
            return False

    async def synthesize_message(self, message_type: str, output_path: str, **kwargs) -> bool:
        """Synthesize a pre-configured message type."""
        if not self.provider or not self.provider.is_initialized:
            self.logger.error("TTS provider not initialized")
            return False

        try:
            text = self.provider.get_message(message_type, **kwargs)

            # Check if file exists and validate it matches expected text
            if os.path.exists(output_path):
                if self.validate_cache_file(text, output_path):
                    self.logger.info(f"Using cached TTS file: {os.path.basename(output_path)} for message '{message_type}'")
                    return True
                else:
                    self.logger.info(f"Cache file invalid for message '{message_type}', regenerating...")
                    self.cache_manager.invalidate_file(output_path)

            # Generate new TTS audio
            self.logger.info(f"Generating new TTS audio for message '{message_type}': '{text}'")
            success = await self.provider.synthesize(text, output_path)

            if success:
                self.logger.info(f"TTS audio generated successfully: {os.path.basename(output_path)}")
                self.cache_manager.add_file(output_path)
            else:
                self.logger.error(f"Failed to generate TTS audio for message '{message_type}'")

            return success

        except Exception as e:
            self.logger.error(f"Error synthesizing message: {e}")
            return False

    async def synthesize_text(self, text: str, output_path: str, **kwargs) -> bool:
        """Synthesize arbitrary text."""
        if not self.provider or not self.provider.is_initialized:
            self.logger.error("TTS provider not initialized")
            return False

        try:
            # Check if file exists and validate it matches expected text
            if os.path.exists(output_path):
                if self.validate_cache_file(text, output_path):
                    self.logger.info(f"Using cached TTS file: {os.path.basename(output_path)} for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
                    return True
                else:
                    self.logger.info(f"Cache file invalid for text, regenerating...")
                    self.cache_manager.invalidate_file(output_path)

            # Generate new TTS audio
            self.logger.info(f"Generating new TTS audio for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
            success = await self.provider.synthesize(text, output_path, **kwargs)

            if success:
                self.logger.info(f"TTS audio generated successfully: {os.path.basename(output_path)}")
                self.cache_manager.add_file(output_path)
            else:
                self.logger.error(f"Failed to generate TTS audio for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")

            return success

        except Exception as e:
            self.logger.error(f"Error synthesizing text: {e}")
            return False

    def generate_cache_path(self, text: str, prefix: str = "tts", suffix: str = ".mp3") -> str:
        """Generate a cache path for TTS audio."""
        cache_dir = self.cache_manager.config.get('directory', '/app/assets')
        # Use full hash for better collision resistance
        text_hash = hashlib.md5(text.encode()).hexdigest()
        filename = f"{prefix}_{self.provider_name}_{text_hash}{suffix}"
        return os.path.join(cache_dir, filename)

    def validate_cache_file(self, expected_text: str, file_path: str) -> bool:
        """Validate that a cached file matches the expected text."""
        if not os.path.exists(file_path):
            return False

        # Extract hash from filename
        filename = os.path.basename(file_path)
        try:
            # Expected format: prefix_provider_hash.extension
            parts = filename.split('_')
            if len(parts) < 3:
                return False

            # Get hash part (remove extension)
            hash_with_ext = parts[2]
            cached_hash = hash_with_ext.split('.')[0]

            # Calculate expected hash
            expected_hash = hashlib.md5(expected_text.encode()).hexdigest()

            return cached_hash == expected_hash

        except (IndexError, AttributeError):
            self.logger.warning(f"Invalid cache filename format: {filename}")
            return False

    @property
    def is_available(self) -> bool:
        """Check if TTS is available and initialized."""
        return self.provider is not None and self.provider.is_initialized
