#!/usr/bin/env python3
"""
Test script for Coqui TTS functionality
"""

import os
import sys
from TTS.api import TTS

def test_coqui_tts():
    """Test Coqui TTS installation and basic functionality."""
    try:
        print("Initializing Coqui TTS...")

        # Initialize TTS with a fast English model
        tts = TTS(model_name="tts_models/en/ljspeech/fast_pitch", progress_bar=True)
        print("✓ Coqui TTS initialized successfully")

        # Test text
        test_text = "Hello, this is a test of Coqui TTS."
        output_path = "/tmp/test_coqui_tts.wav"

        print(f"Generating speech for: '{test_text}'")
        tts.tts_to_file(text=test_text, file_path=output_path)

        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✓ Audio file generated successfully: {output_path} ({file_size} bytes)")

            # Clean up
            os.remove(output_path)
            print("✓ Test file cleaned up")

            return True
        else:
            print("✗ Audio file was not created")
            return False

    except Exception as e:
        print(f"✗ Error testing Coqui TTS: {e}")
        return False

def list_available_models():
    """List available TTS models."""
    try:
        print("\nAvailable TTS models:")
        models = TTS.list_models()

        # Filter for English models
        english_models = [model for model in models if 'en/' in model]

        print("\nEnglish models:")
        for i, model in enumerate(english_models[:10], 1):  # Show first 10
            print(f"  {i}. {model}")

        if len(english_models) > 10:
            print(f"  ... and {len(english_models) - 10} more")

    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    print("Coqui TTS Test Script")
    print("=" * 40)

    # List available models
    list_available_models()

    print("\n" + "=" * 40)
    print("Testing basic TTS functionality...")

    # Test basic functionality
    success = test_coqui_tts()

    if success:
        print("\n✓ All tests passed! Coqui TTS is working correctly.")
        sys.exit(0)
    else:
        print("\n✗ Tests failed. Please check the error messages above.")
        sys.exit(1)
