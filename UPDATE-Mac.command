#!/bin/bash
# ===== 프로그램 업데이트 - 맥 (더블클릭) =====
# GitHub 에서 최신 버전을 받아 이 폴더를 갱신합니다.
# 주의: 프로그램 파일을 최신 버전으로 덮어씁니다. (음성/설정/설치 환경은 유지)
cd "$(dirname "$0")" || exit 1
REPO_URL="https://github.com/sh200220/foreign-video-tts.git"

echo "===== 프로그램 업데이트 (GitHub) ====="

if ! command -v git >/dev/null 2>&1; then
  echo "[안내] git 이 필요합니다. 뜨는 창에서 '설치'를 눌러 명령어 도구를 설치한 뒤 다시 실행하세요."
  xcode-select --install 2>/dev/null
  read -p "엔터를 누르면 창이 닫힙니다..."
  exit 1
fi

if [ ! -d ".git" ]; then
  echo "[처음 한 번] 이 폴더를 GitHub 저장소와 연결합니다..."
  echo "  - 로그인을 물어보면 GitHub 사용자명과 토큰(또는 비밀번호)을 입력하세요."
  rm -rf "${TMPDIR:-/tmp}/fvt-gitlink"
  git clone --no-checkout "$REPO_URL" "${TMPDIR:-/tmp}/fvt-gitlink" || { echo "[오류] 연결 실패"; read -p "엔터..."; exit 1; }
  mv "${TMPDIR:-/tmp}/fvt-gitlink/.git" ".git" || { echo "[오류] 연결 실패"; read -p "엔터..."; exit 1; }
  rm -rf "${TMPDIR:-/tmp}/fvt-gitlink"
fi

if git fetch origin && git reset --hard origin/main; then
  echo ""
  echo "업데이트 완료! START-Mac.command 로 실행하세요."
  echo "(새 기능에 필요한 것이 있으면 시작할 때 자동으로 설치됩니다)"
else
  echo "[오류] 업데이트에 실패했습니다. 인터넷/GitHub 로그인 상태를 확인해 주세요."
fi
read -p "엔터를 누르면 창이 닫힙니다..."
