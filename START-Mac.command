#!/bin/bash
# ===== 외국어 영상 TTS - 맥 (설치 겸 실행, 더블클릭) =====
# 처음 실행하면 필요한 것을 자동으로 설치하고, 이후엔 바로 실행됩니다.
cd "$(dirname "$0")" || exit 1
# 인터넷에서 받은 파일의 '격리(quarantine)' 표시를 풀어 두면 이후 실행이 매끄럽습니다 (best-effort).
xattr -dr com.apple.quarantine "$(pwd)" 2>/dev/null || true

# (1) 이미 설치돼 있으면(.venv) 곧바로 실행
if [ ! -x ".venv/bin/python" ]; then
  # (2) Python 3.11 확인
  if command -v python3.11 >/dev/null 2>&1; then
    PYEXE="python3.11"
  else
    echo ""
    echo "============================================================"
    echo " [안내] 먼저 Python 3.11 을 설치한 뒤 이 파일을 다시 더블클릭하세요."
    echo "   방법 A) https://www.python.org/downloads/release/python-3119/"
    echo "           에서 'macOS 64-bit universal2 installer' 받아 설치"
    echo "   방법 B) Homebrew 가 있으면 터미널에서:  brew install python@3.11"
    echo "============================================================"
    read -p "엔터를 누르면 창이 닫힙니다..."
    exit 1
  fi
  echo "[처음 한 번] 설치 중입니다... 몇 분 걸릴 수 있어요. 이 창을 닫지 마세요."
  "$PYEXE" -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip
  if ! ./.venv/bin/python -m pip install -r requirements.txt; then
    echo "[오류] 설치 중 문제가 발생했습니다. 인터넷 연결을 확인하고 다시 실행하세요."
    read -p "엔터를 누르면 창이 닫힙니다..."
    exit 1
  fi
fi

# 업데이트 대비: 새로 필요한 패키지가 빠져 있으면 자동으로 보충 설치 (약 1초 확인)
if ! ./.venv/bin/python -c "import supertonic, onnxruntime" >/dev/null 2>&1; then
  echo "[업데이트] 새 기능에 필요한 패키지를 설치합니다... 이 창을 닫지 마세요."
  ./.venv/bin/python -m pip install -r requirements.txt
fi

echo "앱을 시작합니다. 잠시 후 브라우저가 열립니다... (이 창을 닫으면 종료)"
./.venv/bin/python app.py
