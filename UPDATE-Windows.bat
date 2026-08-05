@echo off
chcp 65001 >nul
REM ===== 프로그램 업데이트 - 윈도우. 더블클릭 한 번이면 끝 =====
REM GitHub 에서 최신 버전을 받아 이 폴더를 갱신합니다.
REM 프로그램 파일만 최신으로 덮어씁니다.
REM 만든 음성, 참고목소리, 설치된 환경 .venv, 설정은 그대로 유지됩니다.
REM
REM [주의] 이 스크립트는 자기 자신도 최신 버전으로 덮어씁니다.
REM 실행 중인 파일이 바뀌면 창에 이상한 글자가 나오기 때문에,
REM 임시 폴더에 복사본을 만들어 그 복사본이 업데이트를 진행합니다.
if /i "%~1"=="__RUN" goto run
del /f /q "%TEMP%\fvt-update-run.bat" >nul 2>&1
copy /y "%~f0" "%TEMP%\fvt-update-run.bat" >nul 2>&1
if not exist "%TEMP%\fvt-update-run.bat" goto run
REM call 없이 실행 - 여기서 제어가 넘어가고 이 파일은 더 읽지 않습니다.
"%TEMP%\fvt-update-run.bat" __RUN "%~dp0."

:run
if /i "%~1"=="__RUN" cd /d "%~2"
if /i not "%~1"=="__RUN" cd /d "%~dp0"
set REPO_URL=https://github.com/sh200220/foreign-video-tts.git

echo ============================================================
echo  프로그램 업데이트
echo ============================================================
echo.

where git >nul 2>&1
if errorlevel 1 goto nogit

if exist ".git" goto pull

echo [처음 한 번] 이 폴더를 최신 버전 저장소와 연결합니다...
git init >nul 2>&1
if errorlevel 1 goto fail
git remote remove origin >nul 2>&1
git remote add origin %REPO_URL%
if errorlevel 1 goto fail

:pull
echo 최신 버전을 내려받는 중입니다. 잠시만 기다려 주세요...
git fetch origin
if errorlevel 1 goto fail
git reset --hard origin/main
if errorlevel 1 goto fail

echo.
echo ============================================================
echo  업데이트 완료!
echo  이 창을 닫고 START-Windows.bat 을 더블클릭해서 실행하세요.
echo  새 기능에 필요한 것은 시작할 때 자동으로 설치됩니다.
echo ============================================================
pause
exit /b 0

:nogit
where winget >nul 2>&1
if errorlevel 1 goto nowinget
echo 업데이트에 필요한 Git 이 없어 자동 설치를 시도합니다. 1~2분 걸릴 수 있어요...
echo 이 창을 닫지 말고 기다려 주세요.
echo "이 앱이 장치를 변경하도록 허용하시겠습니까?" 창이 뜨면 "예" 를 눌러 주세요.
winget install -e --id Git.Git --silent --accept-package-agreements --accept-source-agreements
echo.
echo ------------------------------------------------------------
echo  Git 설치를 시도했습니다.
echo  이 창을 닫고 UPDATE-Windows.bat 을 "다시" 더블클릭해 주세요.
echo  다시 이 안내가 나오면 자동 설치가 안 된 것이므로,
echo  https://git-scm.com/download/win 에서 Git 을 직접 설치한 뒤
echo  UPDATE-Windows.bat 을 다시 더블클릭하세요.
echo ------------------------------------------------------------
pause
exit /b 1

:nowinget
echo ------------------------------------------------------------
echo  업데이트에 필요한 Git 이 이 PC 에 없습니다.
echo  아래 주소에서 Git 을 설치해 주세요. 설치 화면은 계속 [Next] 만 누르면 됩니다.
echo    https://git-scm.com/download/win
echo  설치가 끝나면 UPDATE-Windows.bat 을 다시 더블클릭하세요.
echo ------------------------------------------------------------
pause
exit /b 1

:fail
echo.
echo ------------------------------------------------------------
echo  [오류] 업데이트에 실패했습니다.
echo   - 인터넷 연결을 확인한 뒤 다시 더블클릭해 주세요.
echo   - 그래도 안 되면 이 창을 화면 캡처해서 보내주세요.
echo ------------------------------------------------------------
pause
exit /b 1
