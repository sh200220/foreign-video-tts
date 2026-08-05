"""
TTS 공용 코어 (Kokoro + Supertonic)
====================================
CLI(tts.py)와 웹 UI(app.py)가 함께 사용하는 음성 생성 핵심 로직.
영어·일본어는 Kokoro-82M, 한국어는 Supertonic(supertonic_engine 모듈)으로 합성한다.

라이선스: Kokoro(Apache 2.0), Supertonic(코드 MIT/모델 OpenRAIL-M) — 모두 상업적 사용 가능.
"""

import re
from pathlib import Path

import numpy as np

import supertonic_engine

SAMPLE_RATE = 24000  # Kokoro 출력 샘플레이트(Hz). 한국어는 sample_rate_for() 참고.

# 표시 이름 -> lang_code / 기본 목소리
#   'a' = American English, 'b' = British English, 'j' = Japanese (Kokoro)
#   'k' = Korean (Supertonic)
LANGS = {
    "영어 (미국)": {"code": "a", "default_voice": "af_heart"},
    "영어 (영국)": {"code": "b", "default_voice": "bf_emma"},
    "일본어":      {"code": "j", "default_voice": "jf_alpha"},
    "한국어":      {"code": "k", "default_voice": "F1"},
}

# Kokoro-82M 목소리 목록 (hexgrad/Kokoro-82M voices/ 기준).
# 이름 첫 글자가 언어(a/b/j), 둘째 글자가 f(여)/m(남).
# 한국어(k)는 Supertonic 프리셋 (F=여, M=남).
VOICES = {
    "a": ["af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica", "af_kore",
          "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
          "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
          "am_michael", "am_onyx", "am_puck", "am_santa"],
    "b": ["bf_emma", "bf_alice", "bf_isabella", "bf_lily",
          "bm_daniel", "bm_fable", "bm_george", "bm_lewis"],
    "j": ["jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro", "jm_kumo"],
    "k": list(supertonic_engine.VOICES),
}

SUPERTONIC_CODES = {"k": supertonic_engine.LANG}  # 내부 코드 -> supertonic 언어 코드


def is_supertonic(lang_code):
    return lang_code in SUPERTONIC_CODES


def sample_rate_for(lang_code):
    """엔진별 출력 샘플레이트 (Kokoro 24k / Supertonic 44.1k)."""
    return supertonic_engine.SAMPLE_RATE if is_supertonic(lang_code) else SAMPLE_RATE


def clamp_speed(lang_code, speed):
    """엔진 허용 범위로 속도 보정. Supertonic 은 0.7~2.0 만 지원."""
    s = float(speed or 1.0)
    if is_supertonic(lang_code):
        return min(supertonic_engine.MAX_SPEED, max(supertonic_engine.MIN_SPEED, s))
    return s

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


def synthesize_segments(text, lang_code, voice, speed=1.0, gap_sec=0.0):
    """텍스트 -> (audio_np, sample_rate, segments).

    segments = [(자막텍스트, 시작초, 끝초)] (줄 단위, 자막/srt 용).
    gap_sec 만큼 줄 사이에 무음을 넣으며 그만큼 타이밍에도 반영한다.
    gap_sec=0 이면 synthesize() 와 동일한 오디오."""
    text = (text or "").strip()
    if not text:
        raise ValueError("대본이 비어 있습니다. 텍스트를 입력해 주세요.")
    pipe = get_pipeline(lang_code)
    gap_len = int(SAMPLE_RATE * max(0.0, gap_sec))
    gap = np.zeros(gap_len, dtype=np.float32) if gap_len > 0 else None
    parts, segments, cursor = [], [], 0.0
    for r in pipe(text, voice=voice, speed=speed, split_pattern=r"\n+"):
        if parts and gap is not None:           # 첫 세그먼트 앞엔 무음 없음
            parts.append(gap)
            cursor += gap_sec
        chunk = _to_numpy(r[2]).astype(np.float32)
        start = cursor
        parts.append(chunk)
        cursor += len(chunk) / SAMPLE_RATE
        seg_text = (r[0] or "").strip()
        if seg_text:
            segments.append((seg_text, start, cursor))
    if not parts:
        raise RuntimeError("오디오가 생성되지 않았습니다.")
    return np.concatenate(parts), SAMPLE_RATE, segments


def normalize_peak(audio, peak=0.97):
    """피크(최대 진폭)를 peak 로 맞춰 클립 간 음량을 비슷하게. (지각 음량 아님)"""
    m = float(np.max(np.abs(audio))) if len(audio) else 0.0
    return (audio / m * peak).astype("float32") if m > 0 else audio


def normalize_lufs(audio, sample_rate, target_lufs=-14.0, peak_ceiling=0.97):
    """방송용 체감 음량(LUFS)으로 정규화 후 피크 제한(클리핑 방지).
    너무 짧거나(0.4초 미만) 측정값이 비유한이면 피크 정규화로 폴백."""
    try:
        import pyloudnorm as pyln
        if len(audio) < int(sample_rate * 0.4):
            return normalize_peak(audio, peak_ceiling)
        x = audio.astype("float64")
        loud = pyln.Meter(sample_rate).integrated_loudness(x)
        if not np.isfinite(loud):
            return normalize_peak(audio, peak_ceiling)
        out = pyln.normalize.loudness(x, loud, target_lufs)
        m = float(np.max(np.abs(out))) if len(out) else 0.0
        if m > peak_ceiling:           # LUFS 보정이 피크를 넘기면 줄여 클리핑 방지
            out = out / m * peak_ceiling
        return out.astype("float32")
    except Exception:
        return normalize_peak(audio, peak_ceiling)


def trim_fade(audio, sample_rate, thresh=0.008, fade_ms=12):
    """앞뒤 무음(임계값 이하)만 잘라내고 짧은 페이드 적용 → (잘린 오디오, 앞에서 자른 초).
    내부의 조용한 구간(드라마틱한 쉼)은 건드리지 않고 가장자리만."""
    if len(audio) == 0:
        return audio, 0.0
    mask = np.abs(audio) > thresh
    if not mask.any():
        return audio, 0.0
    first = int(np.argmax(mask))
    last = len(mask) - int(np.argmax(mask[::-1]))
    out = audio[first:last].astype("float32").copy()
    n = min(int(sample_rate * fade_ms / 1000), len(out) // 2)
    if n > 0:
        ramp = np.linspace(0.0, 1.0, n, dtype="float32")
        out[:n] *= ramp
        out[-n:] *= ramp[::-1]
    return out, first / sample_rate


# --- 인라인 쉼 태그: 대본 속 [쉼:1.5] 위치에 무음 삽입 (전각 콜론 허용, 0~10초) ---

_PAUSE_TAG = re.compile(r"\[쉼[:：]\s*(\d+(?:\.\d+)?)\s*\]")
MAX_PAUSE_SEC = 10.0


def split_pause_tags(line):
    """줄 -> [("text", 조각) | ("pause", 초)] 목록.

    유효한 태그만 처리하고 그 외([쉼:abc] 등)는 일반 텍스트로 남긴다.
    태그가 없으면 [("text", 줄)], 빈 줄이면 []."""
    if not line.strip():
        return []
    parts, pos = [], 0
    for m in _PAUSE_TAG.finditer(line):
        if m.start() > pos:
            parts.append(("text", line[pos:m.start()]))
        sec = min(MAX_PAUSE_SEC, max(0.0, float(m.group(1))))
        if sec > 0:
            parts.append(("pause", sec))
        pos = m.end()
    if pos < len(line):
        parts.append(("text", line[pos:]))
    out = []
    for kind, val in parts:              # 공백뿐인 텍스트 조각 제거
        if kind == "text":
            val = val.strip()
            if not val:
                continue
        out.append((kind, val))
    return out


def strip_pause_tags(line):
    """자막용: 쉼 태그를 지우고 공백 정리."""
    return re.sub(r"\s+", " ", _PAUSE_TAG.sub(" ", line)).strip()


# --- 대화 모드: '이름=목소리' 매핑을 등록하면 '이름:' 줄을 그 목소리로 읽는다 ---

def parse_voice_map(rules):
    """화자 지정 텍스트('이름=목소리' 줄들) -> dict. 형식 오류는 ValueError."""
    vmap = {}
    for ln in (rules or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if "=" not in ln:
            raise ValueError(f"화자 지정 형식이 잘못됐습니다: '{ln}' (예: A=af_heart)")
        name, v = ln.split("=", 1)
        name, v = name.strip(), v.strip()
        if not name or not v:
            raise ValueError(f"화자 지정 형식이 잘못됐습니다: '{ln}' (예: A=af_heart)")
        vmap[name] = v
    return vmap


def match_speaker(line, voice_map):
    """줄이 '등록된이름: 내용'이면 (목소리, 내용), 아니면 (None, 원래 줄).

    반각/전각 콜론, 이름 뒤 공백 허용. 등록 안 된 접두사('참고:' 등)는
    오탐 없이 그대로 둔다."""
    s = line.lstrip()
    for name, voice in (voice_map or {}).items():
        m = re.match(re.escape(name) + r"\s*[:：]\s*(.*)$", s)
        if m:
            return voice, m.group(1).strip()
    return None, line


# --- 자막 줄 규격화: 긴 자막을 최대 글자 수 이하 조각으로 (시간은 글자 수 비례) ---

_BREAK_PUNCT = "、。，．！？!?,.;：:…"


def _wrap_text(text, max_chars):
    """공백 -> 문장부호 -> 강제 순의 경계로 max_chars 이하 조각 리스트."""
    pieces, rest = [], text.strip()
    while len(rest) > max_chars:
        window = rest[:max_chars + 1]
        cut, drop = window.rfind(" "), 1              # 1) 공백 경계(공백은 버림)
        if cut <= 0:
            cut, drop = -1, 0
            for i in range(len(window) - 1, 0, -1):   # 2) 문장부호 경계(부호 포함)
                if window[i - 1] in _BREAK_PUNCT:
                    cut = i
                    break
            if cut <= 0:
                cut = max_chars                       # 3) 강제 분할
        piece = rest[:cut].rstrip()
        if piece:
            pieces.append(piece)
        rest = rest[cut + drop:].lstrip()
    if rest:
        pieces.append(rest)
    return pieces or [text]


def split_segments_for_srt(segments, max_chars):
    """자막 세그먼트를 max_chars 이하로 분할, 시간은 글자 수 비례. 0/None 이면 그대로."""
    if not max_chars or int(max_chars) <= 0:
        return segments
    max_chars = int(max_chars)
    out = []
    for text, start, end in segments:
        pieces = _wrap_text(text, max_chars)
        if len(pieces) <= 1:
            out.append((text, start, end))
            continue
        total = sum(len(p) for p in pieces)
        t = start
        for i, p in enumerate(pieces):
            e = end if i == len(pieces) - 1 else t + (end - start) * len(p) / total
            out.append((p, t, e))
            t = e
    return out


def _srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments, path):
    """segments 를 SRT 자막 파일로 path 에 저장하고 Path 반환."""
    path = Path(path)
    blocks = [f"{i}\n{_srt_time(s)} --> {_srt_time(e)}\n{t}\n"
              for i, (t, s, e) in enumerate(segments, 1)]
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


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

    결과 텐서를 synthesize(text, lang_code, <이 텐서>, speed) 의 voice 로 넘기면 된다.
    Kokoro 전용 — 한국어(Supertonic)는 지원하지 않는다."""
    if is_supertonic(lang_code):
        raise ValueError("목소리 섞기는 한국어에서는 지원되지 않습니다 (Kokoro 전용 기능).")
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
