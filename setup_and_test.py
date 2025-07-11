#!/usr/bin/env python3
"""
Setup and test script for Discord Bellboy Bot with Coqui TTS
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n{description}...")
    print(f"Running: {' '.join(command)}")

    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        if result.stdout:
            print(f"Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed")
        print(f"Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"✗ Command not found: {command[0]}")
        print(f"Please install {command[0]} and ensure it's in your PATH")
        return False

def check_file_exists(file_path, description):
    """Check if a file exists."""
    if os.path.exists(file_path):
        print(f"✓ {description} found: {file_path}")
        return True
    else:
        print(f"✗ {description} not found: {file_path}")
        return False

def main():
    print("Discord Bellboy Bot Setup and Test")
    print("=" * 50)

    # Check Python version
    print(f"Python version: {sys.version}")
    if sys.version_info < (3, 8):
        print("✗ Python 3.8 or higher is required")
        return False
    print("✓ Python version is compatible")

    # Check for requirements.txt
    if not check_file_exists("requirements.txt", "Requirements file"):
        return False

    # Install Python packages
    if not run_command([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                      "Installing Python packages"):
        return False

    # Check system dependencies
    print("\nChecking system dependencies...")

    # Check FFmpeg
    ffmpeg_ok = run_command(["ffmpeg", "-version"], "Checking FFmpeg")

    # Check if .env file exists
    env_exists = check_file_exists(".env", "Environment configuration")
    if not env_exists:
        check_file_exists(".env.example", "Environment example")
        print("Please copy .env.example to .env and configure your settings")

    # Test TTS if possible
    print("\nTesting Coqui TTS...")
    try:
        from TTS.api import TTS
        print("✓ Coqui TTS imported successfully")

        # Try to list models
        try:
            models = TTS.list_models()
            print(f"✓ Found {len(models)} TTS models available")
        except Exception as e:
            print(f"Warning: Could not list TTS models: {e}")

    except ImportError as e:
        print(f"✗ Could not import Coqui TTS: {e}")
        print("Try running: pip install TTS")
        return False

    # Test Discord.py
    try:
        import discord
        print(f"✓ Discord.py {discord.__version__} imported successfully")
    except ImportError as e:
        print(f"✗ Could not import discord.py: {e}")
        return False

    # Summary
    print("\n" + "=" * 50)
    print("Setup Summary:")
    print("✓ Python packages installed")
    if ffmpeg_ok:
        print("✓ FFmpeg is available")
    else:
        print("✗ FFmpeg not found - audio processing will fail")

    if env_exists:
        print("✓ Configuration file (.env) exists")
    else:
        print("✗ Configuration file (.env) needs to be created")

    print("✓ TTS functionality is ready")
    print("✓ Discord functionality is ready")

    if ffmpeg_ok and env_exists:
        print("\n🎉 Setup complete! You can now run the bot with:")
        print("   python app/bellboy.py")
        print("\nOr test TTS first with:")
        print("   python test_coqui_tts.py")
    else:
        print("\n⚠️  Please address the issues above before running the bot")

    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error during setup: {e}")
        sys.exit(1)
