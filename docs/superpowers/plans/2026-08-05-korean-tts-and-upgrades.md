# 한국어 TTS(Supertonic) + 대화 모드·쉼 태그·자막 규격화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kokoro 앱에 Supertonic 기반 한국어 TTS를 추가하고, 화자별 대화 모드·인라인 쉼 태그·자막 줄 규격화를 넣는다.

**Architecture:** `supertonic_engine.py`(신규 소형 래퍼)가 Supertonic 합성을 담당하고, `kokoro_core.py`가 lang_code로 엔진을 분기하는 파사드로 남는다. `synthesize_segments()`를 "줄 단위 렌더 루프"로 리팩터해 대화 모드(줄별 목소리)·쉼 태그(줄 내 무음)를 한 경로로 처리한다. app.py/tts.py의 import·반환 형식은 불변.

**Tech Stack:** supertonic 1.3.1 (ONNX, torch 무관), onnxruntime **1.20.1 고정**, 기존 kokoro 0.9.4 + gradio 6.18.

## Global Constraints

- requirements.txt는 ASCII 전용 (cp949 로케일 파싱 문제).
- onnxruntime==1.20.1 고정 — 이 PC에서 1.22+/1.28은 DLL init 실패(WinError 1114 계열).
- 테스트(tests/test_core.py)는 모델·네트워크 없이 실행 가능해야 한다 (기존 관례).
- Supertonic 실측값: sample_rate=44100, wav shape=(1,N) float32, 목소리 F1~F5/M1~M5,
  speed 허용 0.7~2.0, 한국어 CPS≈6.3(속도 1.0 환산), supertonic 언어 코드 "ko".
- 한국어 UI 문구·주석은 기존 파일들의 한국어 스타일을 따른다.

---

### Task 1: supertonic_engine.py + requirements 고정

**Files:**
- Create: `supertonic_engine.py`
- Modify: `requirements.txt` (끝에 Korean TTS 섹션 추가)

**Interfaces:**
- Produces: `supertonic_engine.SAMPLE_RATE == 44100`, `supertonic_engine.VOICES` (10개 리스트),
  `synth_line(text: str, voice: str, speed: float) -> np.ndarray (float32 1-D)`

- [ ] **Step 1: supertonic_engine.py 작성** — 모듈 레벨에서는 numpy만 import(테스트가 모델 없이 import 가능해야 함). TTS 인스턴스/스타일은 lazy 캐시:

```python
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
```

- [ ] **Step 2: requirements.txt 끝에 추가** (ASCII만):

```
# --- Korean TTS (Supertonic, ONNX-based - independent of torch) ---
# onnxruntime pinned: 1.22+ fails to load on this Windows PC with
# "DLL initialization routine failed" (same class as torch 2.12 c10.dll issue).
# 1.20.1 verified working on Windows; recent versions may work on macOS but
# keep one pinned version everywhere for reproducibility.
supertonic==1.3.1
onnxruntime==1.20.1
```

- [ ] **Step 3: 검증** — `.venv/Scripts/python.exe -c "import supertonic_engine as e; print(e.SAMPLE_RATE, len(e.VOICES))"` → `44100 10`. `pip check` 통과 확인.
- [ ] **Step 4: Commit** `feat: add supertonic engine wrapper for Korean TTS`

---

### Task 2: 코어 순수 헬퍼 (TDD)

**Files:**
- Modify: `kokoro_core.py` (LANGS/VOICES/상수 + 헬퍼 함수들)
- Test: `tests/test_core.py`

**Interfaces:**
- Produces (kokoro_core):
  - `LANGS["한국어"] == {"code": "k", "default_voice": "F1"}` (기존 3개 유지)
  - `SUPERTONIC_CODES == {"k": "ko"}`, `is_supertonic(code) -> bool`
  - `sample_rate_for(code) -> int` (k→44100, 그 외→24000)
  - `clamp_speed(code, speed) -> float` (k만 0.7~2.0 클램프)
  - `split_pause_tags(line) -> list[("text", str) | ("pause", float)]` — `[쉼:1.5]`(전각 콜론 허용, 0~10 클램프)
  - `strip_pause_tags(line) -> str` — 자막용 태그 제거+공백 정리
  - `parse_voice_map(rules) -> dict` — `이름=목소리` 줄들, 형식 오류 시 ValueError
  - `match_speaker(line, voice_map) -> (voice|None, spoken_text)` — 등록된 `이름:`/`이름：` 접두사만 매칭
  - `split_segments_for_srt(segments, max_chars) -> segments` — 공백→문장부호→강제 순 분할, 시간 글자수 비례
  - `blend_voices("k", ...)` → ValueError (모델 로드 전에 가드)

- [ ] **Step 1: 실패하는 테스트 작성** — tests/test_core.py에 추가:

```python
# ---------------- 한국어 엔진 등록/속도 클램프 ----------------

def test_korean_lang_registered():
    assert "한국어" in core.LANGS
    assert core.LANGS["한국어"]["code"] == "k"
    assert core.LANGS["한국어"]["default_voice"] == "F1"
    assert core.voices_for("k") == ["F1", "F2", "F3", "F4", "F5",
                                    "M1", "M2", "M3", "M4", "M5"]

def test_sample_rate_per_engine():
    assert core.sample_rate_for("a") == 24000
    assert core.sample_rate_for("j") == 24000
    assert core.sample_rate_for("k") == 44100

def test_clamp_speed():
    assert core.clamp_speed("k", 0.5) == 0.7
    assert core.clamp_speed("k", 2.5) == 2.0
    assert core.clamp_speed("k", 1.0) == 1.0
    assert core.clamp_speed("a", 0.5) == 0.5      # Kokoro 는 그대로

def test_blend_korean_raises():
    try:
        core.blend_voices("k", "F1", "F2", 0.5)
        assert False, "한국어 blend 는 ValueError 여야 함"
    except ValueError:
        pass

# ---------------- 쉼 태그 ----------------

def test_pause_tags_midline():
    parts = core.split_pause_tags("안녕하세요 [쉼:1.5] 반갑습니다")
    assert parts == [("text", "안녕하세요"), ("pause", 1.5), ("text", "반갑습니다")]

def test_pause_tags_fullwidth_and_clamp():
    assert core.split_pause_tags("[쉼：99]")[0] == ("pause", 10.0)   # 전각 콜론 + 10초 클램프

def test_pause_tags_invalid_kept_as_text():
    assert core.split_pause_tags("[쉼:abc] 본문") == [("text", "[쉼:abc] 본문")]

def test_pause_tags_none():
    assert core.split_pause_tags("그냥 문장") == [("text", "그냥 문장")]

def test_strip_pause_tags_for_caption():
    assert core.strip_pause_tags("앞 [쉼:2] 뒤") == "앞 뒤"

# ---------------- 대화 모드 ----------------

def test_parse_voice_map():
    m = core.parse_voice_map("A=af_heart\n B = am_michael \n\n")
    assert m == {"A": "af_heart", "B": "am_michael"}

def test_parse_voice_map_bad_line_raises():
    try:
        core.parse_voice_map("A-af_heart")
        assert False, "= 없는 줄은 ValueError 여야 함"
    except ValueError:
        pass

def test_match_speaker():
    vm = {"A": "af_heart", "나레이터": "am_adam"}
    assert core.match_speaker("A: 안녕", vm) == ("af_heart", "안녕")
    assert core.match_speaker("나레이터： 시작합니다", vm) == ("am_adam", "시작합니다")
    assert core.match_speaker("참고: 이 줄은 그대로", vm) == (None, "참고: 이 줄은 그대로")
    assert core.match_speaker("콜론 없는 줄", vm) == (None, "콜론 없는 줄")

# ---------------- 자막 줄 규격화 ----------------

def test_srt_split_disabled():
    segs = [("아주 긴 자막 텍스트", 0.0, 5.0)]
    assert core.split_segments_for_srt(segs, 0) == segs

def test_srt_split_space_boundary_and_timing():
    segs = [("hello world again", 0.0, 3.0)]
    out = core.split_segments_for_srt(segs, 11)
    assert [t for t, _, _ in out] == ["hello world", "again"]
    assert out[0][1] == 0.0 and abs(out[-1][2] - 3.0) < 1e-6
    assert abs(out[0][2] - out[1][1]) < 1e-6            # 이어짐
    assert out[0][2] > out[1][2] - out[1][1]            # 긴 조각이 더 긴 시간

def test_srt_split_punct_boundary_cjk():
    segs = [("こんにちは。ようこそ、皆さん", 0.0, 4.0)]
    out = core.split_segments_for_srt(segs, 8)
    assert out[0][0] == "こんにちは。"                    # 문장부호 뒤에서 분할

def test_srt_split_forced():
    segs = [("가나다라마바사아자차", 0.0, 2.0)]
    out = core.split_segments_for_srt(segs, 4)
    assert [t for t, _, _ in out] == ["가나다라", "마바사아", "자차"]
```

- [ ] **Step 2: 실행해 실패 확인** — `.venv\Scripts\python.exe tests\test_core.py` → 새 테스트들 ERROR/FAIL.
- [ ] **Step 3: kokoro_core.py에 구현** — LANGS에 `"한국어": {"code": "k", "default_voice": "F1"}`, VOICES["k"], 그리고:

```python
import supertonic_engine

SUPERTONIC_CODES = {"k": supertonic_engine.LANG}   # 내부 코드 -> supertonic 언어 코드

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

# --- 인라인 쉼 태그: [쉼:1.5] (전각 콜론 허용, 0~10초) ---
_PAUSE_TAG = re.compile(r"\[쉼[:：]\s*(\d+(?:\.\d+)?)\s*\]")
MAX_PAUSE_SEC = 10.0

def split_pause_tags(line):
    """줄 -> [("text", 조각) | ("pause", 초)] 목록. 태그 없으면 [("text", 줄)]."""
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
    for kind, val in parts:               # 공백뿐인 텍스트 조각 제거
        if kind == "text":
            val = val.strip()
            if not val:
                continue
        out.append((kind, val))
    return out or [("text", line.strip())] if line.strip() else []

def strip_pause_tags(line):
    """자막용: 쉼 태그를 지우고 공백 정리."""
    return re.sub(r"\s+", " ", _PAUSE_TAG.sub(" ", line)).strip()

# --- 대화 모드: '이름=목소리' 매핑, '이름:' 줄 매칭 ---

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
    반각/전각 콜론, 이름 뒤 공백 허용. 등록 안 된 접두사는 건드리지 않는다."""
    s = line.lstrip()
    for name, voice in (voice_map or {}).items():
        m = re.match(re.escape(name) + r"\s*[:：]\s*(.*)$", s)
        if m:
            return voice, m.group(1).strip()
    return None, line
```

`split_segments_for_srt` + 내부 `_wrap_text`:

```python
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
```

`blend_voices` 가드(기존 함수 맨 앞):

```python
def blend_voices(lang_code, voice_a, voice_b, ratio):
    if is_supertonic(lang_code):
        raise ValueError("목소리 섞기는 한국어에서는 지원되지 않습니다 (Kokoro 전용 기능).")
    pipe = get_pipeline(lang_code)
    ...
```

- [ ] **Step 4: 테스트 통과 확인** — 전부 PASS.
- [ ] **Step 5: Commit** `feat: core helpers for Korean engine, pause tags, dialogue map, srt wrapping`

---

### Task 3: synthesize_segments 줄 단위 렌더 루프 리팩터

**Files:**
- Modify: `kokoro_core.py` — `synthesize`, `synthesize_segments` 교체 + `_synth_line` 추가

**Interfaces:**
- Consumes: Task 1 `supertonic_engine.synth_line`, Task 2 헬퍼 전부
- Produces: `synthesize_segments(text, lang_code, voice, speed=1.0, gap_sec=0.0, voice_map=None) -> (np.float32[], sr, [(caption, start, end)])`
  — 기존 시그니처에 voice_map 만 추가(하위 호환). `synthesize(text, lang_code, voice, speed=1.0) -> (audio, sr)` 불변.

- [ ] **Step 1: 구현** —

```python
def _synth_line(line_text, lang_code, voice, speed):
    """엔진에 상관없이 '한 줄'을 합성해 float32 1-D 배열 반환."""
    if is_supertonic(lang_code):
        return supertonic_engine.synth_line(line_text, voice, speed)
    pipe = get_pipeline(lang_code)
    chunks = [_to_numpy(r[2]).astype("float32") for r in pipe(line_text, voice=voice, speed=speed)]
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype="float32")


def synthesize_segments(text, lang_code, voice, speed=1.0, gap_sec=0.0, voice_map=None):
    """텍스트 -> (audio_np, sample_rate, segments). 줄 단위 렌더 루프.

    segments = [(자막텍스트, 시작초, 끝초)] — 자막에는 화자 접두사·쉼 태그 제외.
    voice_map: 대화 모드 {'이름': 목소리} — '이름:' 줄을 그 목소리로 읽는다.
    [쉼:초] 태그 위치에는 무음을 넣는다(자막 구간은 말 시작~끝만).
    gap_sec 만큼 줄 사이에 무음을 넣으며 타이밍에도 반영한다."""
    text = (text or "").strip()
    if not text:
        raise ValueError("대본이 비어 있습니다. 텍스트를 입력해 주세요.")
    sr = sample_rate_for(lang_code)
    speed = clamp_speed(lang_code, speed)
    if voice_map:
        valid = voices_for(lang_code)
        for name, v in voice_map.items():
            if v not in valid:
                raise ValueError(
                    f"화자 '{name}'의 목소리 '{v}'가 현재 언어에 없습니다. "
                    f"가능한 목소리: {', '.join(valid)}")
    gap_len = int(sr * max(0.0, gap_sec))
    parts, segments, cursor, first = [], [], 0.0, True
    for raw in re.split(r"\n+", text):
        line = raw.strip()
        if not line:
            continue
        if not first and gap_len > 0:
            parts.append(np.zeros(gap_len, dtype="float32"))
            cursor += gap_len / sr
        first = False
        line_voice, spoken = voice, line
        if voice_map:
            mv, rest = match_speaker(line, voice_map)
            if mv is not None:
                line_voice, spoken = mv, rest
        seg_start, seg_end = None, cursor
        for kind, val in split_pause_tags(spoken):
            if kind == "pause":
                n = int(sr * val)
                parts.append(np.zeros(n, dtype="float32"))
                cursor += n / sr
            else:
                chunk = _synth_line(val, lang_code, line_voice, speed)
                if not len(chunk):
                    continue
                if seg_start is None:
                    seg_start = cursor
                parts.append(chunk)
                cursor += len(chunk) / sr
                seg_end = cursor
        caption = strip_pause_tags(spoken)
        if seg_start is not None and caption:
            segments.append((caption, seg_start, seg_end))
    parts = [p for p in parts if len(p)]
    if not parts or not any(np.abs(p).sum() > 0 for p in parts):
        raise RuntimeError("오디오가 생성되지 않았습니다.")
    return np.concatenate(parts), sr, segments


def synthesize(text, lang_code, voice, speed=1.0):
    """텍스트 -> (audio_np, sample_rate). 빈 텍스트면 ValueError. (segments 없는 래퍼)"""
    audio, sr, _ = synthesize_segments(text, lang_code, voice, speed)
    return audio, sr
```

주의: 기존 `synthesize`/`synthesize_segments` 본문은 제거(대체). `SAMPLE_RATE = 24000` 상수와 docstring 유지.

- [ ] **Step 2: 기존+신규 테스트 전부 통과 확인** (모델 안 쓰는 경로만 실행됨).
- [ ] **Step 3: 실합성 e2e 스모크(수동, 이 PC에서)** — scratchpad 스크립트로 3개 언어 × (기본, 쉼 태그, 대화 모드, gap, srt 분할) 합성해 길이·세그먼트 타이밍 sanity 확인.
- [ ] **Step 4: Commit** `refactor: line-based render loop with engine dispatch, dialogue voices, pause tags`

---

### Task 4: app.py UI 배선

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: core의 `parse_voice_map`, `split_segments_for_srt`, `is_supertonic`, voice_map 파라미터.

- [ ] **Step 1: 상수·초기값** — `CPS["k"] = 6.3`, `PREVIEW_TEXT["k"] = "안녕하세요, 선택한 목소리의 미리듣기입니다."`, 설정 로드에 `INIT_DLG = bool(_s.get("dlg_on", False))`, `INIT_DLG_MAP = _s.get("dlg_map", "") or ""`, `INIT_SRT_MAX = int(...) 0~60 검증(기본 0)`. 헤더 부제 "…일본어와 영어" → "한국어·일본어·영어".
- [ ] **Step 2: 언어 변경 시 목소리 섞기 숨김** — `on_lang_change(lang_label, mix_on_val)`이 `(voice업데이트, voice2업데이트, mix_on 표시여부, mix_row 표시여부)` 반환:

```python
def on_lang_change(lang_label, mix_on_val):
    info = core.LANGS[lang_label]
    voices = core.voices_for(info["code"])
    can_mix = not core.is_supertonic(info["code"])
    return (gr.update(choices=voices, value=info["default_voice"]),
            gr.update(choices=voices, value=_second_voice(voices)),
            gr.update(visible=can_mix),
            gr.update(visible=can_mix and bool(mix_on_val)))
```

초기 렌더도 동일 규칙(INIT_LANG이 한국어면 숨김). `mix_on.change`는 기존 유지하되 `visible=on and can_mix` 로직과 충돌 없게 lang을 입력에 추가.

- [ ] **Step 3: 대화 모드 UI** — 대본 카드의 추가 옵션 아코디언 위에:

```python
dlg_on = gr.Checkbox(value=INIT_DLG, label="대화 모드 — 줄 앞 '이름:' 표시로 화자별 목소리")
with gr.Column(visible=INIT_DLG) as dlg_col:
    dlg_map = gr.Textbox(value=INIT_DLG_MAP, lines=3,
                         label="화자 지정 (한 줄에 하나: 이름=목소리)",
                         info="대본의 '이름: 내용' 줄만 그 목소리로 읽어요. 등록 안 된 줄은 "
                              "기본 목소리로 읽고, 자막에는 이름을 빼고 기록합니다. "
                              "대화 모드 중에는 목소리 섞기가 무시됩니다.",
                         placeholder="A=af_heart\nB=am_michael")
dlg_on.change(lambda on: gr.update(visible=on), inputs=dlg_on, outputs=dlg_col)
```

- [ ] **Step 4: 자막 슬라이더** — srt_on 줄 아래: `srt_max = gr.Slider(0, 60, value=INIT_SRT_MAX, step=1, label="자막 한 줄 최대 글자 수 (0 = 제한 없음)", info="영어 42 / 한국어·일본어 20~24 권장")`
- [ ] **Step 5: generate()/save_pending()/preview() 배선** —
  - generate 시그니처에 `dlg_on, dlg_map, srt_max` 추가(+설정 저장).
  - `use_mix = mix_on and not core.is_supertonic(code) and not dlg_on`; `voice_arg = blend… if use_mix else voice`.
  - `vmap = core.parse_voice_map(dlg_map) if dlg_on else None` (ValueError → gr.Error).
  - synth_one에서 `core.synthesize_segments(..., voice_map=vmap)`, srt 저장 전 `segs = core.split_segments_for_srt(segs, srt_max)` (save_pending도 srt_max 파라미터 추가, pending 저장 시에도 적용).
  - preview()도 `use_mix` 규칙 적용(한국어에서 mix_on이 저장돼 있어도 무시).
- [ ] **Step 6: 도움말 갱신** — 아코디언에 3줄 추가: 대화 모드, `[쉼:1.5]` 태그, 자막 글자 수 + "한국어 첫 생성 시 모델 자동 다운로드(인터넷 1회)".
- [ ] **Step 7: 검증** — `.venv/Scripts/python.exe -c "import app"` (Blocks 구성 오류 없음). 수동: 앱 띄워 한국어 미리듣기/생성/대화/쉼/자막 확인.
- [ ] **Step 8: Commit** `feat: Korean language, dialogue mode, pause tags, srt wrap in web UI`

---

### Task 5: CLI(tts.py) + 샘플 폴더

**Files:**
- Modify: `tts.py`
- Create: `scripts/ko/sample_intro.txt`, `output/ko/.gitkeep`

- [ ] **Step 1: tts.py** — `FOLDER_LANG["ko"] = ("k", "F1")`, `--lang` choices `["en", "ja", "ko", "all"]`, all 목록 `["en", "ja", "ko"]`, 도움말 문구의 'en 또는 ja'를 'en/ja/ko'로. (믹스는 core가 한국어에서 ValueError → 기존 [오류] 출력 경로로 자연 처리)
- [ ] **Step 2: 샘플 대본** — scripts/ko/sample_intro.txt:

```
안녕하세요. 외국어 영상 TTS의 한국어 샘플 대본입니다.
이 파일을 지우고, 만들고 싶은 대본을 .txt 파일로 넣어 주세요.
```

- [ ] **Step 3: 검증** — `python tts.py --lang ko` 실행해 output/ko/*.wav 생성 확인.
- [ ] **Step 4: Commit** `feat: Korean batch support in CLI`

---

### Task 6: 문서 (README, 설치방법.txt)

**Files:**
- Modify: `README.md` — 기능 목록에 한국어·대화 모드·쉼 태그·자막 규격화, 라이선스 절에 Supertonic(코드 MIT/모델 OpenRAIL-M, 상업 가능·유해 용도 금지) 추가.
- Modify: `설치방법.txt` — "이미 설치한 경우: pip install -r requirements.txt 한 번 더" + "한국어 첫 생성 시 모델 자동 다운로드(인터넷 1회)" 안내. CRLF 유지(.gitattributes가 처리).

- [ ] **Step 1: 두 문서 갱신**
- [ ] **Step 2: Commit** `docs: Korean TTS + new features in README and install guide`

---

### Task 7: 최종 검증

- [ ] **Step 1:** `tests\test_core.py` 전체 PASS.
- [ ] **Step 2:** e2e 스크립트(스크래치): 영어/일본어(회귀)·한국어(신규) 각 1클립 + 대화 모드 + 쉼 태그 + srt 분할 + LUFS/트림 조합 생성, 길이·세그먼트 단조증가 assert.
- [ ] **Step 3:** `import app` 및 앱 기동 스모크.
- [ ] **Step 4:** 잔여 커밋 정리, 최종 요약 보고 (+백그라운드 리서치 결과 취합).
