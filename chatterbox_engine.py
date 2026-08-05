"""
Chatterbox 고품질 TTS 엔진 래퍼 (메인 venv 쪽)
===============================================
kokoro_core 가 고품질 모드(lang_code 'ce'/'cj'/'ck')일 때 합성을 위임한다.

Chatterbox 는 의존성이 본 앱과 충돌하므로 별도 가상환경(.venv-chatterbox)에
설치하고, 이 모듈이 상주 워커(chatterbox_worker.py)를 서브프로세스로 띄워
JSON 라인 프로토콜로 통신한다. 워커는 모델을 1회만 로드하고 앱이 살아있는
동안 재사용된다(앱 종료 시 stdin 이 닫혀 함께 종료).

장치: 워커가 CUDA 가능하면 GPU(동업자 PC), 아니면 CPU(느림 — 배치용).
라이선스: Chatterbox(MIT, 상업 사용 가능). 출력에 비가청 워터마크 포함.
"""

import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import numpy as np

SAMPLE_RATE = 24000                       # Chatterbox(S3Gen) 출력 샘플레이트(Hz)
LANGS = {"ce": "en", "cj": "ja", "ck": "ko"}   # 내부 코드 -> chatterbox 언어 코드
DEFAULT_VOICE = "기본 목소리"              # 내장 기본 화자
VOICES = [DEFAULT_VOICE]                  # 기본 목록 (참고목소리 폴더로 확장 — list_voices)
PROMPT_EXTS = (".wav", ".mp3", ".flac", ".ogg", ".m4a")   # 참고 목소리로 인식할 확장자
DEFAULT_EMOTION = 0.5                     # exaggeration 기본값 (0=밋밋 ~ 1=과장)
EMOTION_MIN, EMOTION_MAX = 0.0, 1.0       # UI 슬라이더 범위
DEFAULT_PACE = 0.5                        # cfg_weight 기본값 (낮음=느긋 ~ 높음=빠릿)
PACE_MIN, PACE_MAX = 0.2, 0.8             # UI 슬라이더 범위

_ROOT = Path(__file__).resolve().parent
_VENV_PY = _ROOT / (".venv-chatterbox/Scripts/python.exe" if sys.platform == "win32"
                    else ".venv-chatterbox/bin/python")
_WORKER = _ROOT / "chatterbox_worker.py"
_TMP = Path(tempfile.gettempdir()) / "foreign-video-tts-hq"
VOICES_DIR = _ROOT / "참고목소리"          # 여기에 wav/mp3 를 넣으면 목소리로 등장


def list_voices(voices_dir=None):
    """"기본 목소리" + 참고목소리 폴더의 오디오 파일 이름(확장자 제외) 목록."""
    d = Path(voices_dir) if voices_dir else VOICES_DIR
    names = []
    if d.is_dir():
        names = sorted({p.stem for p in d.iterdir()
                        if p.is_file() and p.suffix.lower() in PROMPT_EXTS})
    return [DEFAULT_VOICE] + names


def _voice_path(voice, voices_dir=None):
    """목소리 이름 -> 참고 오디오 경로 (기본 목소리는 None). 없으면 RuntimeError."""
    if not voice or voice == DEFAULT_VOICE:
        return None
    d = Path(voices_dir) if voices_dir else VOICES_DIR
    for ext in PROMPT_EXTS:
        p = d / f"{voice}{ext}"
        if p.is_file():
            return p
    raise RuntimeError(
        f"참고 목소리 '{voice}' 파일을 찾을 수 없습니다. "
        f"'{d.name}' 폴더에 {voice}.wav (또는 mp3) 가 있는지 확인하고 "
        "목소리 목록을 새로고침해 주세요.")

_proc = None          # 상주 워커 프로세스
_device = None        # 워커가 보고한 장치 ("cuda"/"cpu")

READY_TIMEOUT_SEC = 1800    # 첫 실행은 모델(~3GB) 자동 다운로드 때문에 오래 걸릴 수 있음


def _read_json(proc, max_skip=50):
    """워커 stdout 에서 JSON 라인을 읽는다. 혹시 끼어든 비-JSON 로그 줄은 건너뛴다."""
    for _ in range(max_skip):
        line = proc.stdout.readline()
        if not line:
            return {}
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return {}


def _spawn():
    global _proc, _device
    if not _VENV_PY.exists():
        raise RuntimeError(
            "고품질 모드가 아직 설치되지 않았습니다. 폴더의 "
            "'SETUP-고품질모드' 파일을 한 번 실행해 주세요. "
            "(첫 사용 시 모델 자동 다운로드로 인터넷이 필요합니다)")
    proc = subprocess.Popen(
        [str(_VENV_PY), str(_WORKER)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        encoding="utf-8", errors="replace", cwd=str(_ROOT))
    info = _read_json(proc)                # ready 대기 (모델 로드/다운로드)
    if not info.get("ready"):
        proc.kill()
        raise RuntimeError(
            "고품질 모드 준비에 실패했습니다: "
            f"{info.get('error', '워커가 응답하지 않습니다')} "
            "(첫 사용이면 인터넷 연결을 확인하고 다시 시도해 주세요)")
    if int(info.get("sr", SAMPLE_RATE)) != SAMPLE_RATE:
        proc.kill()
        raise RuntimeError(f"예상치 못한 샘플레이트: {info.get('sr')}")
    _proc, _device = proc, info.get("device")
    return _proc


def _get_proc():
    global _proc
    if _proc is None or _proc.poll() is not None:
        _proc = None
        _spawn()
    return _proc


def device():
    """마지막으로 확인된 합성 장치 ("cuda"/"cpu"/None=미기동)."""
    return _device


def shutdown():
    """상주 워커 종료 (테스트/명시적 정리용; 앱 종료 시엔 자동으로 닫힘)."""
    global _proc
    if _proc is not None and _proc.poll() is None:
        try:
            _proc.stdin.close()
            _proc.wait(timeout=10)
        except Exception:
            _proc.kill()
    _proc = None


def synth_line(text, lang_code, emotion=DEFAULT_EMOTION, pace=DEFAULT_PACE,
               voice=DEFAULT_VOICE):
    """한 줄 합성 -> float32 1-D numpy. lang_code 는 'ce'/'cj'/'ck'.

    emotion = exaggeration(표현 강도), pace = cfg_weight(낮음=느긋, 높음=빠릿).
    자동 보정 없이 사용자가 준 값을 그대로 쓴다.
    voice: "기본 목소리" 또는 참고목소리 폴더의 파일 이름(확장자 제외) — 그 목소리를 복제."""
    import soundfile as sf
    prompt = _voice_path(voice)
    _TMP.mkdir(parents=True, exist_ok=True)
    out = _TMP / f"line_{uuid.uuid4().hex}.wav"
    req = {"text": text, "lang": LANGS[lang_code],
           "exaggeration": float(emotion), "cfg": float(pace),
           "out": str(out),
           "prompt": str(prompt) if prompt else None}
    proc = _get_proc()
    try:
        proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        res = _read_json(proc)
    except OSError as e:
        shutdown()
        raise RuntimeError(f"고품질 워커와의 통신이 끊겼습니다: {e}. 다시 시도해 주세요.")
    if not res:
        shutdown()
        raise RuntimeError("고품질 워커가 종료됐습니다. 다시 시도해 주세요. "
                           "(메모리가 부족하면 다른 프로그램을 닫아 보세요)")
    if not res.get("ok"):
        raise RuntimeError(f"고품질 합성 실패: {res.get('error')}")
    try:
        audio, _sr = sf.read(str(out), dtype="float32")
        return audio.reshape(-1)
    finally:
        try:
            os.remove(out)
        except OSError:
            pass
