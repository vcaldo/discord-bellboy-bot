#!/usr/bin/env python3
"""
Test script to validate New Relic configuration and agent initialization.
Run this before starting the bot to ensure New Relic is properly configured.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_newrelic_config():
    """Test New Relic configuration and initialization."""
    print("🔍 Testing New Relic Configuration...")
    print("=" * 50)

    # Check environment variables
    license_key = os.getenv('NEW_RELIC_LICENSE_KEY')
    app_name = os.getenv('NEW_RELIC_APP_NAME', 'Discord-Bellboy-Bot')
    environment = os.getenv('NEW_RELIC_ENVIRONMENT', 'production')
    config_file = os.getenv('NEW_RELIC_CONFIG_FILE')

    print(f"📋 NEW_RELIC_LICENSE_KEY: {'✅ Set' if license_key else '❌ Not set'}")
    if license_key:
        print(f"   Key preview: {license_key[:8]}...")

    print(f"📋 NEW_RELIC_APP_NAME: {app_name}")
    print(f"📋 NEW_RELIC_ENVIRONMENT: {environment}")
    print(f"📋 NEW_RELIC_CONFIG_FILE: {config_file or 'Not set (using env vars)'}")

    if not license_key:
        print("\n❌ ERROR: NEW_RELIC_LICENSE_KEY is required but not set!")
        print("Please set it in your .env file or environment variables.")
        return False

    # Test New Relic import and initialization
    print("\n🔧 Testing New Relic Agent...")
    try:
        import newrelic.agent
        print("✅ New Relic agent imported successfully")

        # Test application registration
        print("🔄 Attempting to register New Relic application...")
        app = newrelic.agent.register_application(timeout=30.0)

        if app:
            print(f"✅ New Relic application registered successfully!")
            print(f"   App Name: {app.name}")
            print(f"   App ID: {getattr(app, 'app_id', 'Unknown')}")

            # Test basic metrics
            print("🔄 Testing custom metrics...")
            newrelic.agent.record_custom_metric('Custom/Test/Initialization', 1)
            newrelic.agent.add_custom_attributes({
                'test.status': 'success',
                'test.script': 'test_newrelic.py'
            })
            print("✅ Custom metric recorded successfully")

            return True
        else:
            print("❌ New Relic application registration failed")
            print("   This could indicate:")
            print("   - Invalid license key")
            print("   - Network connectivity issues")
            print("   - New Relic service problems")
            return False

    except ImportError:
        print("❌ New Relic agent not found!")
        print("   Please install it with: pip install newrelic")
        return False
    except Exception as e:
        print(f"❌ Error during New Relic initialization: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_file():
    """Test New Relic configuration file if it exists."""
    config_file = os.getenv('NEW_RELIC_CONFIG_FILE', 'newrelic.ini')

    print(f"\n📄 Testing configuration file: {config_file}")

    if os.path.exists(config_file):
        print(f"✅ Configuration file exists: {config_file}")

        # Check if it's readable
        try:
            with open(config_file, 'r') as f:
                content = f.read()
                if 'license_key' in content:
                    print("✅ Configuration file contains license_key setting")
                else:
                    print("⚠️  Configuration file doesn't contain license_key setting")

                if 'app_name' in content:
                    print("✅ Configuration file contains app_name setting")
                else:
                    print("⚠️  Configuration file doesn't contain app_name setting")

        except Exception as e:
            print(f"❌ Error reading configuration file: {e}")

    else:
        print(f"⚠️  Configuration file not found: {config_file}")
        print("   Using environment variables for configuration")

def main():
    """Main test function."""
    print("🚀 New Relic Configuration Test")
    print("This script will test your New Relic setup for the Discord Bot")
    print("=" * 60)

    # Test configuration file
    test_config_file()

    # Test New Relic configuration
    success = test_newrelic_config()

    print("\n" + "=" * 60)
    if success:
        print("🎉 SUCCESS: New Relic is properly configured!")
        print("You should see data in your New Relic dashboard within a few minutes.")
        print("Dashboard: https://one.newrelic.com")
    else:
        print("💥 FAILURE: New Relic configuration has issues!")
        print("Please fix the above issues before running the bot.")

    print("\n💡 Tips:")
    print("- Make sure your license key is valid and starts with 'NRAL-'")
    print("- Check that you have network connectivity to New Relic")
    print("- Verify your .env file contains the correct NEW_RELIC_LICENSE_KEY")
    print("- When running with Docker, ensure environment variables are passed correctly")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
