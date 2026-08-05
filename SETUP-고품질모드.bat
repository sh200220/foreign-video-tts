@echo off
chcp 65001 >nul
REM ===== 고품질(감정) 모드 설치 - 윈도우 (한 번만 실행) =====
REM Chatterbox 엔진을 별도 환경(.venv-chatterbox)에 설치합니다.
REM NVIDIA 그래픽카드가 있으면 자동으로 GPU 가속 버전을 설치합니다.
cd /d "%~dp0"

echo ===== 고품질(감정) 모드 설치 =====
if exist ".venv-chatterbox\Scripts\python.exe" goto pip

py -3.11 -m venv .venv-chatterbox
if errorlevel 1 (
  echo [오류] Python 3.11 이 필요합니다. START-Windows.bat 을 먼저 한 번 실행해 주세요.
  pause
  exit /b 1
)

:pip
".venv-chatterbox\Scripts\python.exe" -m pip install --upgrade pip

where nvidia-smi >nul 2>&1
if %errorlevel%==0 (
  echo NVIDIA 그래픽카드 감지 - GPU 가속 버전으로 설치합니다.
  ".venv-chatterbox\Scripts\python.exe" -m pip install "torch==2.6.0+cu124" "torchaudio==2.6.0+cu124" --index-url https://download.pytorch.org/whl/cu124
) else (
  echo 그래픽카드가 없어 CPU 버전으로 설치합니다. 생성이 느립니다.
  ".venv-chatterbox\Scripts\python.exe" -m pip install "torch==2.6.0" "torchaudio==2.6.0" --index-url https://download.pytorch.org/whl/cpu
)
if errorlevel 1 goto fail

".venv-chatterbox\Scripts\python.exe" -m pip install chatterbox-tts==0.1.7
if errorlevel 1 goto fail

".venv-chatterbox\Scripts\python.exe" -c "import torch, chatterbox; print('설치 확인 OK / GPU 사용 가능:', torch.cuda.is_available())"
echo.
echo 설치 완료! 앱에서 '... (고품질·감정)' 언어를 고르면 됩니다.
echo 첫 생성 때 모델 약 3GB 를 자동 다운로드합니다. (인터넷 필요, 한 번만)
pause
exit /b 0

:fail
echo [오류] 설치 중 문제가 발생했습니다. 인터넷 연결을 확인하고 다시 실행해 주세요.
pause
exit /b 1
