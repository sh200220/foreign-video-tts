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
    """텍스트 -> (audio_np, sample_rate). 빈 텍스트면 ValueError.

    voice 는 프리셋 이름(str) 또는 blend_voices 가 만든 스타일 텐서 둘 다 가능
    (Kokoro 파이프라인이 FloatTensor 를 그대로 수용)."""
    text = (text or "").strip()
    if not text:
        raise ValueError("대본이 비어 있습니다. 텍스트를 입력해 주세요.")
    pipe = get_pipeline(lang_code)
    chunks = [_to_numpy(a) for _, _, a in pipe(text, voice=voice, speed=speed, split_pattern=r"\n+")]
    if not chunks:
        raise RuntimeError("오디오가 생성되지 않았습니다.")
    return np.concatenate(chunks), SAMPLE_RATE


# --- 목소리 믹스(blend) ---

def blend_style(style_a, style_b, ratio):
    """두 목소리 스타일 텐서를 ratio*A + (1-ratio)*B 로 섞어 반환.

    ratio 는 목소리 A 비중(0~1): 1.0=완전 A, 0.0=완전 B, 0.5=균등.
    범위 밖이거나 두 텐서 모양이 다르면 ValueError."""
    if not 0.0 <= ratio <= 1.0:
        raise ValueError(f"믹스 비율은 0~1 사이여야 합니다: {ratio}")
    if tuple(style_a.shape) != tuple(style_b.shape):
        raise ValueError(
            f"목소리 텐서 모양이 다릅니다: {tuple(style_a.shape)} vs {tuple(style_b.shape)}")
    return ratio * style_a + (1.0 - ratio) * style_b


def blend_voices(lang_code, voice_a, voice_b, ratio):
    """같은 언어의 두 프리셋 목소리를 섞은 스타일 텐서 반환.

    결과 텐서를 synthesize(text, lang_code, <이 텐서>, speed) 의 voice 로 넘기면 된다."""
    pipe = get_pipeline(lang_code)
    return blend_style(pipe.load_voice(voice_a), pipe.load_voice(voice_b), ratio)


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


# 표시 이름 -> 파일 확장자. soundfile(libsndfile) 가 확장자로 인코딩을 정함.
# WAV=편집용 무손실, MP3=공유·미리듣기, FLAC=무손실 압축, OGG=개방형 압축.
FORMATS = {"WAV": ".wav", "MP3": ".mp3", "FLAC": ".flac", "OGG": ".ogg"}


def save_audio(audio, sample_rate, folder, name, fmt="WAV"):
    """audio를 folder에 name.<ext>로 저장하고 Path 반환.

    fmt 는 FORMATS 의 키(대소문자 무시). 충돌 시 ' (2)' … 자동 증가."""
    import soundfile as sf
    key = (fmt or "WAV").upper()
    if key not in FORMATS:
        raise ValueError(f"지원하지 않는 포맷입니다: {fmt} (가능: {', '.join(FORMATS)})")
    path = unique_path(folder, sanitize_filename(name), ext=FORMATS[key])
    sf.write(str(path), audio, sample_rate)
    return path


def save_wav(audio, sample_rate, folder, name):
    """하위호환 래퍼: WAV 로 저장."""
    return save_audio(audio, sample_rate, folder, name, "WAV")
