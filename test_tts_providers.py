#!/usr/bin/env python3
"""
Test script for TTS providers in Discord Bellboy Bot.

This script tests the availability and functionality of different TTS providers.
"""

import os
import sys
import logging
import tempfile
from pathlib import Path

# Add the app directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from tts.tts_manager import TTSManager
from tts.providers import TTSProviderFactory


def setup_logging():
    """Setup logging for the test script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def test_provider_factory(logger):
    """Test the provider factory functionality."""
    logger.info("Testing TTS Provider Factory...")

    # Test getting available providers
    providers = TTSProviderFactory.get_available_providers()
    logger.info(f"Available providers: {providers}")

    # Test all providers
    results = TTSProviderFactory.test_all_providers(logger)
    logger.info("Provider availability test results:")
    for provider, available in results.items():
        status = "✓ Available" if available else "✗ Not Available"
        logger.info(f"  {provider}: {status}")

    return results


def test_tts_manager(logger):
    """Test the TTS Manager functionality."""
    logger.info("Testing TTS Manager...")

    # Create TTS manager with default provider
    tts_manager = TTSManager(logger)

    # Check availability
    if not tts_manager.is_available:
        logger.warning("No TTS providers available - skipping functionality tests")
        return False

    # Get provider info
    info = tts_manager.get_provider_info()
    logger.info(f"Current provider: {info['name']}")
    logger.info(f"Supported formats: {info['supported_formats']}")

    # Test TTS generation
    test_text = "Hello, this is a test of the TTS system."

    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = os.path.join(temp_dir, "test_tts.mp3")

        logger.info(f"Generating TTS for: '{test_text}'")
        success = tts_manager.create_tts_mp3(test_text, output_path)

        if success and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logger.info(f"✓ TTS generation successful! File size: {file_size} bytes")
        else:
            logger.error("✗ TTS generation failed!")
            return False

    # Test cache stats
    cache_stats = tts_manager.get_cache_stats()
    logger.info(f"Cache stats: {cache_stats}")

    return True


def test_provider_switching(logger):
    """Test switching between different providers."""
    logger.info("Testing provider switching...")

    # Get available providers
    available_providers = TTSProviderFactory.test_all_providers(logger)
    working_providers = [name for name, available in available_providers.items() if available]

    if len(working_providers) < 2:
        logger.warning("Need at least 2 working providers to test switching")
        return True

    tts_manager = TTSManager(logger)

    for provider_name in working_providers[:2]:  # Test first 2 available providers
        logger.info(f"Switching to provider: {provider_name}")
        success = tts_manager.switch_provider(provider_name)

        if success:
            info = tts_manager.get_provider_info()
            logger.info(f"✓ Successfully switched to: {info['name']}")

            # Test generation with this provider
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = os.path.join(temp_dir, f"test_{provider_name}.mp3")
                success = tts_manager.create_tts_mp3("Provider switching test", output_path)

                if success:
                    logger.info(f"✓ TTS generation successful with {provider_name}")
                else:
                    logger.error(f"✗ TTS generation failed with {provider_name}")
        else:
            logger.error(f"✗ Failed to switch to: {provider_name}")

    return True


def test_user_tts_methods(logger):
    """Test the user join/leave/move TTS methods."""
    logger.info("Testing user TTS methods...")

    tts_manager = TTSManager(logger)

    if not tts_manager.is_available:
        logger.warning("No TTS providers available - skipping user TTS tests")
        return False

    test_user_id = 12345
    test_display_name = "TestUser"

    # Test join TTS
    join_path = tts_manager.create_user_join_tts(test_display_name, test_user_id)
    if join_path and os.path.exists(join_path):
        logger.info(f"✓ User join TTS created: {join_path}")
    else:
        logger.error("✗ User join TTS failed")
        return False

    # Test leave TTS
    leave_path = tts_manager.create_user_leave_tts(test_display_name, test_user_id)
    if leave_path and os.path.exists(leave_path):
        logger.info(f"✓ User leave TTS created: {leave_path}")
    else:
        logger.error("✗ User leave TTS failed")
        return False

    # Test move TTS
    move_path = tts_manager.create_user_move_tts(test_display_name, test_user_id)
    if move_path and os.path.exists(move_path):
        logger.info(f"✓ User move TTS created: {move_path}")
    else:
        logger.error("✗ User move TTS failed")
        return False

    # Clean up test files
    for path in [join_path, leave_path, move_path]:
        if path and os.path.exists(path):
            os.remove(path)
            logger.debug(f"Cleaned up test file: {path}")

    return True


def main():
    """Main test function."""
    logger = setup_logging()
    logger.info("Starting TTS Provider Tests...")

    # Ensure assets directory exists
    assets_dir = Path("app/assets")
    assets_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Test provider factory
        provider_results = test_provider_factory(logger)

        # Test TTS manager
        tts_success = test_tts_manager(logger)

        # Test provider switching
        switch_success = test_provider_switching(logger)

        # Test user TTS methods
        user_tts_success = test_user_tts_methods(logger)

        # Summary
        logger.info("=" * 50)
        logger.info("Test Summary:")
        logger.info(f"Available providers: {list(provider_results.keys())}")
        logger.info(f"Working providers: {[name for name, available in provider_results.items() if available]}")
        logger.info(f"TTS Manager: {'✓' if tts_success else '✗'}")
        logger.info(f"Provider Switching: {'✓' if switch_success else '✗'}")
        logger.info(f"User TTS Methods: {'✓' if user_tts_success else '✗'}")

        if any(provider_results.values()):
            logger.info("🎉 At least one TTS provider is working!")
        else:
            logger.warning("⚠️  No TTS providers are currently working")
            logger.info("Make sure you have installed at least one TTS library:")
            logger.info("  - Coqui TTS: pip install TTS")
            logger.info("  - Piper TTS: pip install piper-tts")
            logger.info("  - MeloTTS: pip install melo-tts")

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
