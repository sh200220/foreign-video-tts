"""
Kokoro TTS 공용 코어
=====================
CLI(tts.py)와 웹 UI(app.py)가 함께 사용하는 음성 생성 핵심 로직.

라이선스: Kokoro(Apache 2.0) — 상업적 사용 가능.
"""

import re
from pathlib import Path

import numpy as np

SAMPLE_RATE = 24000  # Kokoro 출력 샘플레이트(Hz)

# 표시 이름 -> Kokoro lang_code / 기본 목소리
#   'a' = American English, 'b' = British English, 'j' = Japanese
LANGS = {
    "영어 (미국)": {"code": "a", "default_voice": "af_heart"},
    "영어 (영국)": {"code": "b", "default_voice": "bf_emma"},
    "일본어":      {"code": "j", "default_voice": "jf_alpha"},
}

# Kokoro-82M 목소리 목록 (hexgrad/Kokoro-82M voices/ 기준).
# 이름 첫 글자가 언어(a/b/j), 둘째 글자가 f(여)/m(남).
VOICES = {
    "a": ["af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica", "af_kore",
          "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
          "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
          "am_michael", "am_onyx", "am_puck", "am_santa"],
    "b": ["bf_emma", "bf_alice", "bf_isabella", "bf_lily",
          "bm_daniel", "bm_fable", "bm_george", "bm_lewis"],
    "j": ["jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo"],
}

_PIPELINES = {}  # lang_code -> KPipeline (언어별 1회 로드 후 캐시)


def get_pipeline(lang_code):
    if lang_code not in _PIPELINES:
        from kokoro import KPipeline
        _PIPELINES[lang_code] = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")
    return _PIPELINES[lang_code]


def voices_for(lang_code):
    return VOICES.get(lang_code, [])


def _to_numpy(audio):
    if hasattr(audio, "detach"):
        return audio.detach().cpu().numpy()
    return np.asarray(audio)


def synthesize(text, lang_code, voice, speed=1.0):
    """텍스트 -> (audio_np, sample_rate). 빈 텍스트면 ValueError."""
    text = (text or "").strip()
    if not text:
        raise ValueError("대본이 비어 있습니다. 텍스트를 입력해 주세요.")
    pipe = get_pipeline(lang_code)
    chunks = [_to_numpy(a) for _, _, a in pipe(text, voice=voice, speed=speed, split_pattern=r"\n+")]
    if not chunks:
        raise RuntimeError("오디오가 생성되지 않았습니다.")
    return np.concatenate(chunks), SAMPLE_RATE


# --- 파일 저장 헬퍼 ---

_ILLEGAL = re.compile(r'[\\/:*?"<>|]')


def sanitize_filename(name, fallback="output"):
    """파일명에서 금지문자 제거. 비면 fallback."""
    name = _ILLEGAL.sub("", (name or "")).strip().rstrip(".")
    return name or fallback


def unique_path(folder, name, ext=".wav"):
    """folder/name.ext 경로. 이미 있으면 ' (2)', ' (3)' … 붙여 덮어쓰기 방지. 폴더는 자동 생성."""
    folder = Path(folder).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / f"{name}{ext}"
    i = 2
    while candidate.exists():
        candidate = folder / f"{name} ({i}){ext}"
        i += 1
    return candidate


def save_wav(audio, sample_rate, folder, name):
    """audio를 folder에 name.wav로 저장하고 Path 반환."""
    import soundfile as sf
    path = unique_path(folder, sanitize_filename(name))
    sf.write(str(path), audio, sample_rate)
    return path
