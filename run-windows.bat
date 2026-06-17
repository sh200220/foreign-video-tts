@echo off
REM ===== 외국어 영상 TTS - 윈도우 실행 =====
cd /d "%~dp0"
echo 앱을 시작합니다. 잠시 후 브라우저가 자동으로 열립니다...
echo (이 창을 닫으면 앱이 종료됩니다.)
".venv\Scripts\python.exe" app.py
pause
