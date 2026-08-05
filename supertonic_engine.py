"""
Supertonic 한국어 TTS 엔진 래퍼
================================
kokoro_core 가 한국어(lang_code 'k')일 때 합성을 이 모듈로 위임한다.

라이선스: Supertonic 예제 코드 MIT, 모델 OpenRAIL-M — 상업적 사용 가능
(불법·유해 용도 금지 조항). 첫 사용 시 HuggingFace 에서 모델을 자동
다운로드하며(인터넷 1회 필요), 이후에는 오프라인으로 동작한다.
"""

import numpy as np

SAMPLE_RATE = 44100          # Supertonic 3 출력 샘플레이트(Hz)
LANG = "ko"                  # supertonic 언어 코드
VOICES = ["F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5"]
MIN_SPEED, MAX_SPEED = 0.7, 2.0   # supertonic.core 허용 범위

_tts = None                  # TTS 인스턴스 (1회 로드 후 캐시)
_styles = {}                 # voice 이름 -> Style 캐시


def _get_tts():
    global _tts
    if _tts is None:
        try:
            from supertonic import TTS
        except ImportError:
            raise RuntimeError(
                "한국어 TTS(supertonic)가 설치되어 있지 않습니다. 터미널에서 "
                "'pip install -r requirements.txt' 를 다시 실행해 주세요.")
        try:
            _tts = TTS(auto_download=True)
        except Exception as e:
            raise RuntimeError(
                "한국어 모델을 준비하지 못했습니다. 첫 사용 시에는 모델 자동 "
                f"다운로드를 위해 인터넷 연결이 필요합니다. (원인: {e})")
    return _tts


def _get_style(voice):
    if voice not in _styles:
        _styles[voice] = _get_tts().get_voice_style(voice)
    return _styles[voice]


def synth_line(text, voice, speed):
    """한 줄 합성 -> float32 1-D numpy. speed 는 0.7~2.0(코어에서 보정 후 전달)."""
    wav, _dur = _get_tts().synthesize(
        text, voice_style=_get_style(voice), lang=LANG, speed=float(speed))
    return np.asarray(wav, dtype="float32").reshape(-1)
