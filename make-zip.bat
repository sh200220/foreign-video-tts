@echo off
chcp 65001 >nul
REM ===== 동업자에게 줄 배포용 ZIP 만들기 (개발자용) =====
REM 주의: git archive 는 "커밋된" 내용만 담습니다. 코드를 바꿨다면 먼저 커밋하세요.
cd /d "%~dp0"

if not exist dist mkdir dist
echo 깨끗한 배포용 ZIP 을 만드는 중... (.venv / .git / 캐시 / 생성된 음성 제외)
git archive --format=zip -o "dist\foreign-video-tts.zip" HEAD
if errorlevel 1 (
  echo.
  echo [오류] git archive 실패. git 저장소가 맞는지, 커밋이 있는지 확인하세요.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  완료:  dist\foreign-video-tts.zip
echo  이 파일을 동업자에게 전달하세요 (구글드라이브 / USB / 메신저).
echo  동업자는 압축을 풀고:
echo    - 윈도우: START-Windows.bat 더블클릭
echo    - 맥:     START-Mac.command 더블클릭 (첫 실행 안내는 README 참고)
echo ============================================================
pause
