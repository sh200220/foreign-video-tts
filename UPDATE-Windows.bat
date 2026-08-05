@echo off
chcp 65001 >nul
REM ===== 프로그램 업데이트 - 윈도우 (더블클릭) =====
REM GitHub 에서 최신 버전을 받아 이 폴더를 갱신합니다.
REM 주의: 이 폴더의 프로그램 파일을 최신 버전으로 덮어씁니다.
REM       (생성한 음성, 설치된 환경(.venv), 설정은 그대로 유지됩니다)
cd /d "%~dp0"
set REPO_URL=https://github.com/sh200220/foreign-video-tts.git

echo ===== 프로그램 업데이트 (GitHub) =====

where git >nul 2>&1
if errorlevel 1 (
  echo Git 이 없어 자동 설치를 시도합니다...
  winget install -e --id Git.Git --silent --accept-package-agreements --accept-source-agreements
  echo.
  echo Git 설치가 끝났습니다. 이 창을 닫고 UPDATE-Windows.bat 을 "다시" 더블클릭하세요.
  echo (자동 설치가 안 됐다면 https://git-scm.com 에서 설치 후 다시 실행)
  pause
  exit /b 1
)

if exist ".git" goto pull
echo [처음 한 번] 이 폴더를 GitHub 저장소와 연결합니다...
echo   - 브라우저 로그인 창이 뜨면 GitHub 계정으로 로그인해 주세요. (한 번만)
if exist "%TEMP%\fvt-gitlink" rmdir /s /q "%TEMP%\fvt-gitlink"
git clone --no-checkout %REPO_URL% "%TEMP%\fvt-gitlink"
if errorlevel 1 goto fail
move "%TEMP%\fvt-gitlink\.git" ".git" >nul
if errorlevel 1 goto fail
rmdir /s /q "%TEMP%\fvt-gitlink" 2>nul

:pull
git fetch origin
if errorlevel 1 goto fail
git reset --hard origin/main
if errorlevel 1 goto fail
echo.
echo 업데이트 완료! START-Windows.bat 으로 실행하세요.
echo (새 기능에 필요한 것이 있으면 시작할 때 자동으로 설치됩니다)
pause
exit /b 0

:fail
echo.
echo [오류] 업데이트에 실패했습니다.
echo  - 인터넷 연결을 확인해 주세요.
echo  - 브라우저 GitHub 로그인 창이 떴다면 로그인 후 다시 실행해 주세요.
echo  - 초대(협업자) 수락을 아직 안 했다면 이메일의 초대를 먼저 수락해 주세요.
pause
exit /b 1
