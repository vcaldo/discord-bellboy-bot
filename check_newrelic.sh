#!/bin/bash

# New Relic Environment Check Script
# Run this inside the Docker container to verify New Relic setup

echo "🔍 New Relic Environment Check"
echo "=============================="

echo "📋 Environment Variables:"
echo "NEW_RELIC_LICENSE_KEY: ${NEW_RELIC_LICENSE_KEY:0:8}..."
echo "NEW_RELIC_APP_NAME: ${NEW_RELIC_APP_NAME:-Discord-Bellboy-Bot}"
echo "NEW_RELIC_ENVIRONMENT: ${NEW_RELIC_ENVIRONMENT:-production}"
echo "NEW_RELIC_CONFIG_FILE: ${NEW_RELIC_CONFIG_FILE:-Not set}"

echo ""
echo "📄 Configuration File Check:"
if [ -f "/app/newrelic.ini" ]; then
    echo "✅ newrelic.ini exists"
    if grep -q "license_key" /app/newrelic.ini; then
        echo "✅ license_key found in config"
    else
        echo "❌ license_key not found in config"
    fi
else
    echo "❌ newrelic.ini not found"
fi

echo ""
echo "🐍 Python New Relic Test:"
python3 -c "
try:
    import newrelic.agent
    print('✅ New Relic agent imported successfully')

    app = newrelic.agent.register_application(timeout=10.0)
    if app:
        print('✅ New Relic application registered:', app.name)
        newrelic.agent.record_custom_metric('Custom/Test/DockerCheck', 1)
        print('✅ Test metric recorded')
    else:
        print('❌ Application registration failed')

except ImportError as e:
    print('❌ New Relic import failed:', e)
except Exception as e:
    print('❌ New Relic test failed:', e)
"

echo ""
echo "🔧 Process Check:"
if pgrep -f "newrelic-admin" > /dev/null; then
    echo "✅ newrelic-admin process is running"
else
    echo "❌ newrelic-admin process not found"
fi

echo ""
echo "📡 Network Test:"
if curl -s --max-time 5 https://collector.newrelic.com > /dev/null; then
    echo "✅ Can reach New Relic collector"
else
    echo "❌ Cannot reach New Relic collector"
fi
