#!/bin/bash
# ===== 외국어 영상 TTS - 맥 설치 (처음 한 번만) =====
cd "$(dirname "$0")" || exit 1
echo "[1/2] 가상환경(.venv) 생성 중..."
python3 -m venv .venv
echo "[2/2] 필요한 프로그램 설치 중... (몇 분 걸릴 수 있어요)"
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
echo ""
echo "============================================"
echo " 설치 완료! 이제 run-mac.command 를 더블클릭하세요."
echo "============================================"
