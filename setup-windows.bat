@echo off
REM ===== 외국어 영상 TTS - 윈도우 설치 (처음 한 번만) =====
cd /d "%~dp0"
echo [1/2] 가상환경(.venv) 생성 중...
python -m venv .venv
echo [2/2] 필요한 프로그램 설치 중... (몇 분 걸릴 수 있어요)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo ============================================
echo  설치 완료! 이제 run-windows.bat 을 더블클릭하세요.
echo ============================================
pause
