#!/bin/bash
# ===== 고품질(감정) 모드 설치 - 맥 (한 번만 실행) =====
# Chatterbox 엔진을 별도 환경(.venv-chatterbox)에 설치합니다. (맥은 CPU 합성 - 느림)
cd "$(dirname "$0")" || exit 1

echo "===== 고품질(감정) 모드 설치 ====="
if [ ! -x ".venv-chatterbox/bin/python" ]; then
  if ! command -v python3.11 >/dev/null 2>&1; then
    echo "[안내] Python 3.11 이 필요합니다. START-Mac.command 를 먼저 한 번 실행해 주세요."
    read -p "엔터를 누르면 창이 닫힙니다..."
    exit 1
  fi
  python3.11 -m venv .venv-chatterbox
fi

./.venv-chatterbox/bin/python -m pip install --upgrade pip
if ./.venv-chatterbox/bin/python -m pip install "torch==2.6.0" "torchaudio==2.6.0" \
   && ./.venv-chatterbox/bin/python -m pip install chatterbox-tts==0.1.7; then
  ./.venv-chatterbox/bin/python -c "import torch, chatterbox; print('설치 확인 OK')"
  echo ""
  echo "설치 완료! 앱에서 '... (고품질·감정)' 언어를 고르면 됩니다."
  echo "첫 생성 때 모델 약 3GB 를 자동 다운로드합니다. (인터넷 필요, 한 번만)"
else
  echo "[오류] 설치 중 문제가 발생했습니다. 인터넷 연결을 확인하고 다시 실행해 주세요."
fi
read -p "엔터를 누르면 창이 닫힙니다..."
