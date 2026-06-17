@echo off
chcp 65001 >nul
REM ===== 외국어 영상 TTS - 윈도우 (설치 겸 실행, 더블클릭) =====
REM 처음 더블클릭하면 필요한 것을 자동으로 설치하고, 이후엔 바로 실행됩니다.
cd /d "%~dp0"

REM (1) 이미 설치돼 있으면(.venv) 곧바로 실행
if exist ".venv\Scripts\python.exe" goto run

REM (2) Python 3.11 확인 — 없으면 winget 으로 자동 설치 시도
echo Python 3.11 을(를) 확인하는 중...
py -3.11 -c "import sys" >nul 2>&1
if %errorlevel%==0 goto makevenv

echo Python 3.11 이(가) 없어 자동 설치를 시도합니다 (winget)...
winget install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
py -3.11 -c "import sys" >nul 2>&1
if %errorlevel%==0 goto makevenv

echo.
echo ============================================================
echo  [안내] Python 3.11 자동 설치가 끝났거나 실패했습니다.
echo   - 방금 설치됐다면: 이 창을 닫고 START-Windows.bat 을 다시 더블클릭하세요.
echo   - 안 됐다면: 아래에서 직접 설치 후 다시 더블클릭하세요.
echo       https://www.python.org/downloads/release/python-3119/
echo       (Windows installer 64-bit, 설치 화면에서 "Add python.exe to PATH" 체크)
echo ============================================================
pause
exit /b 1

:makevenv
echo [처음 한 번] 설치 중입니다... 몇 분 걸릴 수 있어요. 이 창을 닫지 마세요.
py -3.11 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [오류] 설치 중 문제가 발생했습니다. 인터넷 연결을 확인하고 다시 실행하세요.
  pause
  exit /b 1
)

:run
echo 앱을 시작합니다. 잠시 후 브라우저가 자동으로 열립니다...
echo (이 창을 닫으면 앱이 종료됩니다.)
".venv\Scripts\python.exe" app.py
pause
