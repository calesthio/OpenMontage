@echo off
REM Start the Chrome that flow_video drives, on the profile that holds the Flow
REM session. Opening Chrome from the normal shortcut uses the DEFAULT profile
REM instead and looks exactly like a lost login.
python "%~dp0scripts\flow_chrome.py" %*
pause
