#!/bin/bash
# Launch unified automation browser for Higgsfield AI (with Apple Sign-In already saved)

PROFILE_DIR="$HOME/.automation-browser/chrome-profile"

echo "🔐 Launching unified Chrome automation browser..."
echo "📍 Using profile: $PROFILE_DIR"
echo ""
echo "Instructions:"
echo "1. Chrome will open to https://higgsfield.ai"
echo "2. If not logged in, click 'Sign in with Apple' and complete auth"
echo "3. Leave Chrome RUNNING in the background"
echo "4. The browser will stay available for automated video generation"
echo ""

# Kill any existing Chrome instances on port 9222 to avoid conflicts
pkill -f "remote-debugging-port=9222" 2>/dev/null || true
sleep 1

# Launch Chrome with unified profile and remote debugging enabled
# Keep it running in the background
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --user-data-dir="$PROFILE_DIR" \
  --remote-debugging-port=9222 \
  https://higgsfield.ai &

CHROME_PID=$!

echo "⏳ Chrome launched with PID $CHROME_PID"
echo "🔗 Remote debugging available at: http://localhost:9222"
echo ""
echo "✅ Browser is ready. Keep this window open while generating videos."
echo "✅ Run: python3 scripts/higgsfield-video-generator.py --generate brief-id"
echo ""
echo "Press Ctrl+C to stop the browser when done generating videos."

wait $CHROME_PID
