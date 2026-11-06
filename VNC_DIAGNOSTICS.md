# VNC Diagnostics Report

## Chain Configuration

| Component | Version | Port | Status |
|-----------|---------|------|--------|
| Xvfb | 2:21.1.16-1.3+deb13u4 | :99 | RUNNING |
| x11vnc | (system) | 5900 | RUNNING |
| websockify | (system) | 6080 | RUNNING |
| noVNC | 1.6.0-2 | 6080 | RUNNING |
| Chrome Stable | 156.0.8078.79 | — | RUNNING |

## Process Details

```
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset
x11vnc -display :99 -rfbauth /home/vscode/.vnc/passwd -forever -shared -rfbport 5900 -bg -logfile /home/vscode/x11vnc.log -cursor
websockify --web /usr/share/novnc 6080 localhost:5900
google-chrome-stable --no-sandbox --disable-gpu --disable-dev-shm-usage --user-data-dir=/home/vscode/chrome-profile-vnc-test --window-size=1920x1080 --start-maximized file:///home/vscode/test-click.html
```

## Verified

- Port 5900: x11vnc listening (VNC RFB protocol)
- Port 6080: websockify+noVNC listening (WebSocket to VNC bridge)
- Port 9223: Chrome DevTools Protocol available
- x11vnc started WITHOUT `-viewonly` flag (input events enabled)
- Cursor updates enabled with `-cursor` flag
- Single x11vnc instance running (no conflicts)
- DISPLAY=:99 consistent across Xvfb, x11vnc, and Chrome

## noVNC Access Link

**https://unhallowed-spooky-hobgoblin-qv5p94wpj5r3xw69-6080.app.github.dev**

**VNC Password:** `OpenMontageVnc2026!`

## Test Page

**File:** `/home/vscode/test-click.html`

The test page displays:
- Large clickable button with counter
- Mouse/touch/pointer event logging
- Visual feedback on click

## Instructions for Android Testing

1. Open the noVNC link above in Chrome on Android
2. Enter password: `OpenMontageVnc2026!`
3. Click the "Fullscreen" button in noVNC toolbar to give VNC focus
4. Tap the large red "Click Me!" button
5. Verify the counter increments and events appear in the log
