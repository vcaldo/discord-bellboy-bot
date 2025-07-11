import os
from typing import Optional
from dotenv import load_dotenv


class Config:
    """Configuration class that reads from environment variables and .env file."""

    def __init__(self):
        # Load .env file if it exists
        load_dotenv()

        self._discord_token: Optional[str] = None
        self._guild_id: Optional[int] = None
        self._log_level: str = "INFO"
        self._auto_join_busiest: bool = True

        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from environment variables."""
        # Discord token (required)
        self._discord_token = os.getenv('DISCORD_TOKEN')

        # Guild ID (optional)
        guild_id_str = os.getenv('GUILD_ID')
        if guild_id_str and guild_id_str.strip():
            try:
                self._guild_id = int(guild_id_str)
            except ValueError:
                print(f"Warning: Invalid GUILD_ID '{guild_id_str}'. Using None (all servers).")

        # Log level (optional, defaults to INFO)
        self._log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        if self._log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            print(f"Warning: Invalid LOG_LEVEL '{self._log_level}'. Using INFO.")
            self._log_level = 'INFO'

        # Auto join busiest channel (optional, defaults to True)
        auto_join_str = os.getenv('AUTO_JOIN_BUSIEST', 'true').lower()
        self._auto_join_busiest = auto_join_str in ['true', '1', 'yes', 'on']

    @property
    def discord_token(self) -> str:
        """Get Discord bot token."""
        if not self._discord_token:
            raise ValueError("DISCORD_TOKEN is required but not set in environment variables or .env file")
        return self._discord_token

    @property
    def guild_id(self) -> Optional[int]:
        """Get Guild ID (Server ID). Returns None if not set (logs all servers)."""
        return self._guild_id

    @property
    def log_level(self) -> str:
        """Get log level."""
        return self._log_level

    @property
    def auto_join_busiest(self) -> bool:
        """Get auto join busiest channel setting."""
        return self._auto_join_busiest

    def validate(self) -> bool:
        """Validate that all required configuration is present."""
        try:
            # Check if discord token is available
            _ = self.discord_token
            return True
        except ValueError as e:
            print(f"Configuration error: {e}")
            return False


# Global config instance
config = Config()
