"""Docker health check script for the Bellboy bot.

Reads the health status file written by the bot's background loop and checks:
1. The health file exists and was recently written (bot process is alive and looping)
2. The bot has successfully connected to Discord (bot_ready=True)

Exit 0 = healthy, Exit 1 = unhealthy.
"""
import json
import sys
import time

HEALTH_FILE = '/tmp/bellboy_health.json'
MAX_STALE_SECONDS = 60  # if health file is older than this, the bot is stuck


def main() -> int:
    try:
        with open(HEALTH_FILE, 'r') as f:
            health = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Health file missing or corrupt — bot hasn't started writing yet
        return 1

    ts = health.get('timestamp', 0)
    age = time.time() - ts

    if age > MAX_STALE_SECONDS:
        print(f"Health file is {age:.0f}s old (limit {MAX_STALE_SECONDS}s)")
        return 1

    if not health.get('bot_ready', False):
        print("Bot not ready yet")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
