#!/usr/bin/env python3
"""
Test script to verify Discord bot token and connection.
"""
import asyncio
import discord
from config import config


async def test_token():
    """Test if the Discord token is valid."""
    try:
        print("Testing Discord token...")
        print(f"Token loaded: {'✓' if config.discord_token else '✗'}")
        
        if config.discord_token:
            # Mask the token for security (show only first and last 6 characters)
            masked_token = f"{config.discord_token[:6]}...{config.discord_token[-6:]}"
            print(f"Token: {masked_token}")
        
        # Test connection
        client = discord.Client(intents=discord.Intents.default())
        
        @client.event
        async def on_ready():
            print(f"✓ Successfully connected as {client.user}")
            print(f"Bot ID: {client.user.id}")
            print(f"Connected to {len(client.guilds)} guilds")
            await client.close()
        
        print("Attempting to connect...")
        await client.start(config.discord_token)
        
    except discord.LoginFailure:
        print("✗ Token is invalid or expired")
        print("Please check:")
        print("1. Your token is correctly copied from Discord Developer Portal")
        print("2. The bot hasn't been regenerated/reset")
        print("3. There are no extra spaces or characters in the .env file")
    except Exception as e:
        print(f"✗ Connection error: {e}")


def main():
    """Main function."""
    try:
        # Test configuration
        if not config.validate():
            return
        
        # Test token
        asyncio.run(test_token())
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
