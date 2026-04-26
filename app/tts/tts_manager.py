"""
Edge TTS manager for Discord Bellboy Bot.
"""
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    edge_tts = None


class EdgeTTSProvider:
    """Edge TTS provider implementation using Microsoft neural voices."""

    provider_name = "edge"

    def __init__(self, config: Dict[str, Any], cache_manager: 'TTSCacheManager'):
        self.config = config
        self.cache_manager = cache_manager
        self.logger = logging.getLogger('bellboy.tts.edge')
        self.is_initialized = False

    async def initialize(self) -> bool:
        """Initialize Edge TTS."""
        if not EDGE_TTS_AVAILABLE:
            self.logger.warning("edge-tts not available - install with: pip install edge-tts")
            return False

        self.is_initialized = True
        self.logger.info("Edge TTS initialized successfully")
        return True

    async def synthesize(self, text: str, output_path: str, **kwargs) -> bool:
        """Synthesize text using Edge TTS."""
        if not self.is_initialized:
            self.logger.error("Edge TTS not initialized")
            return False

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            voice = self.config.get('voice', 'pt-PT-DuarteNeural')
            self.logger.debug(f"Starting Edge TTS synthesis for text length: {len(text)} characters")
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            self.logger.debug(f"Edge TTS synthesis completed: {os.path.basename(output_path)}")
            return True
        except Exception as e:
            self.logger.error(f"Edge TTS synthesis failed: {e}")
            return False

    def get_message(self, message_type: str, **kwargs) -> str:
        """Get a formatted message for the given type."""
        messages = self.config.get('messages', {})
        member_id = kwargs.get('member_id')

        if member_id and self._is_special_user(str(member_id)):
            template = messages.get(f"{message_type}_alt", messages.get(message_type, f"{message_type} {{display_name}}"))
        else:
            template = messages.get(message_type, f"{message_type} {{display_name}}")

        if isinstance(template, list):
            template = template[int(time.time() * 1000) % len(template)]

        return template.format(**kwargs)

    def _is_special_user(self, user_id: str) -> bool:
        """Check if a user ID is in the special users list."""
        special_users = os.getenv('SPECIAL_USERS', '')
        if not special_users.strip():
            return False

        special_user_ids = [uid.strip() for uid in special_users.split(',') if uid.strip()]
        return user_id in special_user_ids


class TTSCacheManager:
    """Manages TTS file caching."""

    def __init__(self, cache_config: Dict[str, Any]):
        self.config = cache_config
        self.cache = {}  # filepath -> timestamp
        self.logger = logging.getLogger('bellboy.tts.cache')

        cache_dir = self.config.get('directory', '/app/assets')
        os.makedirs(cache_dir, exist_ok=True)

        env_max = os.getenv('TTS_CACHE_MAX_SIZE_MB')
        if env_max is not None:
            max_size_mb = int(env_max)
        else:
            max_size_mb = self.config.get('max_size_mb', 1024)
        self.max_size_bytes = max_size_mb * 1024 * 1024

        enabled = self.config.get('enabled', True)
        self.logger.info(f"TTS Cache initialized: enabled={enabled}, max_size_mb={max_size_mb}, directory={cache_dir}")

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

    def _get_total_size(self) -> int:
        """Calculate total size in bytes of all tracked cache files."""
        total = 0
        for file_path in self.cache:
            try:
                if os.path.exists(file_path):
                    total += os.path.getsize(file_path)
            except OSError:
                pass
        return total

    def _cleanup_if_needed(self) -> None:
        """Clean up old cache files if size limit exceeded."""
        total_size = self._get_total_size()

        if total_size <= self.max_size_bytes:
            return

        max_size_mb = self.max_size_bytes / (1024 * 1024)
        self.logger.info(
            f"Cache size limit exceeded ({total_size / (1024*1024):.1f}MB/{max_size_mb:.0f}MB), "
            f"cleaning up oldest files"
        )

        sorted_cache = sorted(self.cache.items(), key=lambda x: x[1])
        for file_path, _ in sorted_cache:
            if total_size <= self.max_size_bytes:
                break
            try:
                file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.cache[file_path]
                total_size -= file_size
                self.logger.debug(f"Removed old cache file: {os.path.basename(file_path)}")
            except OSError as e:
                self.logger.warning(f"Could not remove cache file {os.path.basename(file_path)}: {e}")

        self.logger.info(f"Cache cleanup completed. Current size: {total_size / (1024*1024):.1f}MB/{max_size_mb:.0f}MB")

    def _scan_existing_cache(self) -> None:
        """Scan cache directory for existing files and add them to tracking."""
        if not self.config.get('enabled', True):
            return

        cache_dir = self.config.get('directory', '/app/assets')
        try:
            if os.path.exists(cache_dir):
                import glob

                existing_files = glob.glob(os.path.join(cache_dir, '*.mp3'))
                current_time = time.time()

                for file_path in existing_files:
                    if os.path.isfile(file_path):
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
        max_size_mb = round(self.max_size_bytes / (1024 * 1024), 0)
        total_size = self._get_total_size()
        total_size_mb = round(total_size / (1024 * 1024), 2)

        return {
            'enabled': self.config.get('enabled', True),
            'directory': cache_dir,
            'max_size_mb': max_size_mb,
            'current_files': len(self.cache),
            'total_size_mb': total_size_mb,
            'usage_percent': round((total_size / self.max_size_bytes) * 100, 1) if self.max_size_bytes > 0 else 0,
        }


class TTSManager:
    """Main TTS manager for Edge TTS."""

    provider_name = "edge"

    def __init__(self, config_path: str = "tts-config.yaml"):
        self.logger = logging.getLogger('bellboy.tts')
        self.config = self._load_config(config_path)
        self.cache_manager = TTSCacheManager(self.config.get('cache', {}))
        self.provider: Optional[EdgeTTSProvider] = None

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load TTS configuration from YAML file."""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                self.logger.warning(f"Config file not found: {config_path}, using defaults")
                return self._get_default_config()

            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                self.logger.info(f"Loaded TTS config from: {config_path}")
                return config

        except Exception as e:
            self.logger.error(f"Error loading TTS config: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if file loading fails."""
        return {
            'providers': {
                'edge': {
                    'name': 'Edge TTS',
                    'enabled': True,
                    'voice': 'pt-PT-DuarteNeural',
                    'settings': {
                        'output_format': 'mp3',
                    },
                    'messages': {
                        'join': ['Bem vindo {display_name}', 'Olha o {display_name} chegando!'],
                        'leave': ['Deus te acompanhe, {display_name}', 'Falou {display_name}, ate mais'],
                        'move': ['O tal do {display_name} trocou de canal'],
                    },
                }
            },
            'cache': {
                'enabled': True,
                'max_size_mb': 1024,
                'directory': '/app/assets',
            },
        }

    async def initialize(self) -> bool:
        """Initialize Edge TTS."""
        try:
            providers_config = self.config.get('providers', {})
            provider_config = providers_config.get(self.provider_name)

            if not provider_config:
                self.logger.error("Edge TTS provider configuration not found")
                return False

            if not provider_config.get('enabled', False):
                self.logger.error("Edge TTS provider is disabled")
                return False

            self.provider = EdgeTTSProvider(provider_config, self.cache_manager)
            success = await self.provider.initialize()
            if success:
                self.logger.info("TTS Manager initialized with Edge TTS")
            else:
                self.logger.error("Failed to initialize Edge TTS")

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
            return await self.synthesize_text(text, output_path, **kwargs)
        except Exception as e:
            self.logger.error(f"Error synthesizing message: {e}")
            return False

    async def synthesize_text(self, text: str, output_path: str, **kwargs) -> bool:
        """Synthesize arbitrary text."""
        if not self.provider or not self.provider.is_initialized:
            self.logger.error("TTS provider not initialized")
            return False

        try:
            if os.path.exists(output_path):
                if self.validate_cache_file(text, output_path):
                    self.logger.info(f"Using cached TTS file: {os.path.basename(output_path)} for text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
                    return True

                self.logger.info("Cache file invalid for text, regenerating...")
                self.cache_manager.invalidate_file(output_path)

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
        text_hash = hashlib.md5(text.encode()).hexdigest()
        filename = f"{prefix}_{self.provider_name}_{text_hash}{suffix}"
        return os.path.join(cache_dir, filename)

    def validate_cache_file(self, expected_text: str, file_path: str) -> bool:
        """Validate that a cached file matches the expected text."""
        if not os.path.exists(file_path):
            return False

        filename = os.path.basename(file_path)
        try:
            hash_with_ext = filename.rsplit('_', 1)[1]
            cached_hash = os.path.splitext(hash_with_ext)[0]
            expected_hash = hashlib.md5(expected_text.encode()).hexdigest()
            return cached_hash == expected_hash
        except (IndexError, AttributeError):
            self.logger.warning(f"Invalid cache filename format: {filename}")
            return False

    def get_message(self, message_type: str, **kwargs) -> Optional[str]:
        """Get a formatted message for the given type via Edge TTS."""
        if not self.provider:
            return None
        return self.provider.get_message(message_type, **kwargs)

    @property
    def is_available(self) -> bool:
        """Check if TTS is available and initialized."""
        return self.provider is not None and self.provider.is_initialized
