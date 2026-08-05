"""
외국어 영상 TTS — 웹 UI (Gradio)
=================================
브라우저에서 언어·목소리·속도를 고르고 대본(또는 .txt 파일 여러 개)을 넣으면
음성을 만들어 원하는 폴더에 원하는 이름·포맷(WAV/MP3/FLAC/OGG)으로 저장한다.
목소리 두 개를 비율로 섞을 수도 있다. (음성 생성은 kokoro_core 공유)

디자인: Pretendard 글꼴 + azure(#00aaff) 액센트.
실행:  python app.py   (브라우저가 자동으로 열립니다)
"""

import html
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import gradio as gr

import kokoro_core as core

DEFAULT_OUTPUT = str((Path(__file__).resolve().parent / "output").resolve())
LANG_LABELS = list(core.LANGS.keys())
FIRST_LANG = LANG_LABELS[0]
FORMAT_LABELS = list(core.FORMATS.keys())

# 자동저장 OFF일 때 '미저장 미리듣기'용 임시 폴더 (브라우저 재생 전용; 실제 저장은 [저장] 버튼)
PREVIEW_DIR = str(Path(tempfile.gettempdir()) / "foreign-video-tts-preview")

# 실측 기반 대략치 (chars/sec, 속도 1.0): 영어 13.6 / 일본어 5.6 / 한국어 6.3
# 고품질(Chatterbox) 모드는 파일럿 실측 근사치.
CPS = {"a": 13.6, "b": 13.6, "j": 5.6, "k": 6.3, "ce": 16.0, "cj": 8.7, "ck": 8.7}

# 목소리 미리듣기용 짧은 샘플 문장 (언어별)
PREVIEW_TEXT = {
    "a": "This is a preview of the selected voice.",
    "b": "This is a preview of the selected voice.",
    "j": "これは、選んだ声のプレビューです。",
    "k": "안녕하세요, 선택한 목소리의 미리듣기입니다.",
    "ce": "This is a preview of the high quality voice.",
    "cj": "これは、高品質モードの声のプレビューです。",
    "ck": "안녕하세요, 고품질 모드 목소리의 미리듣기입니다.",
}

SETTINGS_PATH = Path.home() / ".foreign-video-tts.json"

# [취소] 버튼이 세우는 협조적 취소 깃발 — 진행 중인 줄까지만 만들고 멈춘다
CANCEL_EVENT = threading.Event()


def load_settings():
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data):
    try:
        SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _second_voice(voices):
    """기본 '목소리 2'는 '목소리 1' 기본값과 겹치지 않게 두 번째 항목으로."""
    return voices[1] if len(voices) > 1 else voices[0]


# --- 저장된 설정을 불러와 '검증된' 초기값 계산 (잘못된 값이면 기본값으로 폴백) ---
_s = load_settings()
INIT_LANG = _s.get("lang") if _s.get("lang") in LANG_LABELS else FIRST_LANG
_init_code = core.LANGS[INIT_LANG]["code"]
INIT_VOICES = core.voices_for(_init_code)
_def_voice = core.LANGS[INIT_LANG]["default_voice"]
INIT_VOICE = _s.get("voice") if _s.get("voice") in INIT_VOICES else _def_voice
INIT_VOICE2 = _s.get("voice2") if _s.get("voice2") in INIT_VOICES else _second_voice(INIT_VOICES)
try:
    INIT_SPEED = float(_s.get("speed", 1.0))
except (TypeError, ValueError):
    INIT_SPEED = 1.0
INIT_SPEED = INIT_SPEED if 0.5 <= INIT_SPEED <= 2.0 else 1.0
INIT_FMT = _s.get("fmt") if _s.get("fmt") in FORMAT_LABELS else "WAV"
INIT_FOLDER = _s.get("folder") or DEFAULT_OUTPUT
INIT_MIX = bool(_s.get("mix_on", False))
INIT_TS = bool(_s.get("add_ts", False))
INIT_SRT = bool(_s.get("srt_on", False))
NORM_MODES = ["끔", "피크", "방송용 (LUFS)"]
_nm = _s.get("norm_mode")
if _nm not in NORM_MODES:                       # 구버전 설정(normalize_on bool) 호환
    _nm = "피크" if _s.get("normalize_on") else "끔"
INIT_NORM = _nm
try:
    INIT_GAP = float(_s.get("gap_sec", 0.0))
except (TypeError, ValueError):
    INIT_GAP = 0.0
INIT_GAP = INIT_GAP if 0.0 <= INIT_GAP <= 2.0 else 0.0
INIT_REPLACE = _s.get("replace_rules", "") or ""
INIT_TRIM = bool(_s.get("trim_on", False))
INIT_SCENE = bool(_s.get("scene_split", False))
INIT_AUTOSAVE = bool(_s.get("autosave", True))   # 생성 시 자동 저장 (기본 ON; 끄면 [저장] 버튼으로)
INIT_DLG = bool(_s.get("dlg_on", False))         # 대화 모드 (화자별 목소리)
# 화자 슬롯 4개: [[이름, 목소리], ...]. 구버전 텍스트 매핑(dlg_map)은 슬롯으로 이전.
_spk_raw = _s.get("spk") or []
if not _spk_raw and (_s.get("dlg_map") or "").strip():
    try:
        _spk_raw = [[k, v] for k, v in core.parse_voice_map(_s["dlg_map"]).items()]
    except ValueError:
        _spk_raw = []
INIT_SPK = [["", None] for _ in range(4)]
for _i, _item in enumerate(_spk_raw[:4]):
    try:
        _nm, _vv = str(_item[0]).strip(), str(_item[1]).strip()
    except (TypeError, IndexError):
        continue
    if _nm and _nm != core.RESET_NAME:
        INIT_SPK[_i] = [_nm, _vv if _vv in INIT_VOICES else None]
try:
    INIT_SRT_MAX = int(_s.get("srt_max", 0))     # 자막 한 줄 최대 글자 수 (0=제한 없음)
except (TypeError, ValueError):
    INIT_SRT_MAX = 0
INIT_SRT_MAX = INIT_SRT_MAX if 0 <= INIT_SRT_MAX <= 60 else 0
INIT_CAN_MIX = core.supports_mix(_init_code)        # 목소리 섞기는 Kokoro 언어에서만
try:
    INIT_EMOTION = float(_s.get("emotion", 0.5))    # 고품질 모드 감정 강도
except (TypeError, ValueError):
    INIT_EMOTION = 0.5
INIT_EMOTION = INIT_EMOTION if 0.0 <= INIT_EMOTION <= 1.0 else 0.5
try:
    INIT_PACE = float(_s.get("pace", 0.5))          # 고품질 모드 말 페이스(cfg)
except (TypeError, ValueError):
    INIT_PACE = 0.5
INIT_PACE = INIT_PACE if 0.2 <= INIT_PACE <= 0.8 else 0.5
INIT_IS_CB = core.is_chatterbox(_init_code)         # 고품질 모드면 속도 대신 감정·페이스 슬라이더
try:
    INIT_TAKES = int(_s.get("takes", 1))            # 테이크 수 (같은 대본 여러 번 생성)
except (TypeError, ValueError):
    INIT_TAKES = 1
INIT_TAKES = INIT_TAKES if 1 <= INIT_TAKES <= 5 else 1

# Pretendard 웹폰트 (인터넷 필요; 없으면 시스템 폰트로 자연 폴백)
HEAD = (
    '<link rel="stylesheet" '
    'href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@latest/dist/web/static/pretendard.css">'
)

HEADER_HTML = """
<div class="app-head">
  <div class="bar"></div>
  <div class="brand"><span class="mark"></span><span class="name">외국어 영상 TTS</span></div>
  <p class="sub">내레이션 음성 생성 · 한국어 / 일본어 / 영어 · 고품질 감정 모드 (Kokoro · Supertonic · Chatterbox)</p>
</div>
"""

CSS = """
/* 배경: 화면 전체를 mist 색으로 (좌우 흰 여백 제거) */
html,body,gradio-app,.gradio-container{background:#f4f8fb!important;}

.gradio-container{
  --primary-50:#e9f7ff;--primary-100:#d3efff;--primary-200:#a6dfff;--primary-300:#79ceff;
  --primary-400:#4cbdff;--primary-500:#00aaff;--primary-600:#0098e5;--primary-700:#0086cc;
  --primary-800:#0a6aa0;--primary-900:#0b4f78;
  --color-accent:#00aaff;--color-accent-soft:#e9f7ff;
  --body-background-fill:#f4f8fb;--background-fill-primary:#ffffff;--background-fill-secondary:#f4f8fb;
  --body-text-color:#0e1c28;--body-text-color-subdued:#5b6b78;
  --block-background-fill:#ffffff;--block-border-color:#e4ebf1;--block-radius:14px;
  --block-label-text-color:#5b6b78;--block-title-text-color:#0e1c28;
  --input-background-fill:#ffffff;--input-border-color:#dae3ea;--input-border-color-focus:#00aaff;
  --input-radius:10px;
  --checkbox-background-color-selected:#00aaff;--checkbox-border-color-selected:#00aaff;
  --slider-color:#00aaff;--link-text-color:#0098e5;--link-text-color-hover:#0086cc;
  --button-primary-background-fill:#00aaff;--button-primary-background-fill-hover:#0098e5;
  --button-primary-text-color:#ffffff;--button-primary-border-color:#00aaff;
  --font:'Pretendard','Apple SD Gothic Neo',system-ui,-apple-system,sans-serif;
  max-width:860px!important;margin:0 auto!important;padding:0 20px 56px!important;
}
body,.gradio-container{font-family:'Pretendard','Apple SD Gothic Neo',system-ui,-apple-system,sans-serif!important;}
footer{display:none!important;}

.app-head{padding:42px 4px 20px;}
.app-head .bar{height:4px;width:46px;border-radius:99px;background:linear-gradient(90deg,#00aaff,#67c9ff);margin-bottom:18px;}
.app-head .brand{display:flex;align-items:center;gap:11px;}
.app-head .mark{width:22px;height:22px;border-radius:6px;background:linear-gradient(135deg,#00aaff,#36bdff);box-shadow:0 4px 12px rgba(0,170,255,.35);}
.app-head .name{font-size:27px;font-weight:800;letter-spacing:-.03em;color:#0e1c28;line-height:1;}
.app-head .sub{margin:13px 0 0;color:#5b6b78;font-size:14.5px;font-weight:500;letter-spacing:-.01em;}

.card{border:1px solid #e4ebf1!important;border-radius:16px!important;background:#fff!important;
  padding:18px!important;margin-bottom:16px!important;
  box-shadow:0 1px 2px rgba(14,28,40,.04),0 10px 28px rgba(14,28,40,.045)!important;}

.gradio-container label span{font-weight:600!important;color:#33454f!important;letter-spacing:-.01em;}

/* 글자 수/예상 길이 — 작고 옅게, 카드에 자연스럽게 (Gradio styler 회색 배경 제거) */
.stats{background:transparent!important;border:none!important;box-shadow:none!important;padding:0!important;min-height:0!important;}
/* Gradio 그룹 styler 의 회색 배경 제거 — 카드(흰색)가 비치게. 작은 버튼/짧은 텍스트 뒤 회색 막대 방지 */
.gradio-container .styler{background:transparent!important;}
.stats p{margin:4px 2px 0!important;color:#8595a1!important;font-size:12.5px!important;font-weight:500!important;letter-spacing:-.01em;}
.hint p{margin:0 0 8px!important;color:#5b6b78!important;font-size:12.5px!important;line-height:1.6;}

.generate-btn button,button.generate-btn{
  font-size:16px!important;font-weight:700!important;letter-spacing:-.01em;
  padding:15px 20px!important;border-radius:12px!important;
  background:#00aaff!important;color:#fff!important;border:none!important;
  box-shadow:0 8px 22px rgba(0,170,255,.30)!important;
  transition:transform .12s ease,box-shadow .12s ease,background .12s ease;}
.generate-btn button:hover{background:#0098e5!important;transform:translateY(-1px);box-shadow:0 12px 28px rgba(0,170,255,.40)!important;}
.generate-btn button:active{transform:translateY(0);}

#status:empty{display:none;}
.status-ok{display:inline-flex;align-items:center;gap:10px;font-weight:600;color:#0e1c28;
  background:#e9f7ff;border:1px solid #bfe8ff;border-radius:11px;padding:10px 14px;font-size:14px;letter-spacing:-.01em;}
.status-ok::before{content:"";width:8px;height:8px;border-radius:50%;background:#00aaff;box-shadow:0 0 0 4px rgba(0,170,255,.18);}
.status-ok code{background:#fff;border:1px solid #d6e6f2;border-radius:6px;padding:2px 8px;color:#0086cc;font-size:13px;}
.stat-list{margin-top:9px;color:#5b6b78;font-size:12.5px;line-height:1.8;}
.stat-list code{background:#fff;border:1px solid #e0e8ef;border-radius:5px;padding:1px 6px;color:#0086cc;}
#recent:empty{display:none;}
.recent{margin-top:14px;}
.recent b{font-size:12.5px;color:#5b6b78;font-weight:700;letter-spacing:-.01em;}

.folder-tools{gap:8px!important;}
.folder-tools button{font-weight:600!important;}
.preview-btn{flex:0 0 auto!important;}
/* 미리듣기 플레이어 테두리를 결과 플레이어와 동일한 연회색으로 (autoplay 의 검은 테두리 제거) */
.preview-audio{border:1px solid #e4ebf1!important;outline:none!important;}

.gradio-container input:focus,.gradio-container textarea:focus,.gradio-container select:focus{
  border-color:#00aaff!important;box-shadow:0 0 0 3px rgba(0,170,255,.16)!important;}

/* 결과(오디오) 영역의 장식 음표만 숨김 — 재생/다운로드 컨트롤·업로드 아이콘은 유지 */
.audio-out label svg{display:none!important;}
.audio-out .empty svg{display:none!important;}

@media (prefers-reduced-motion: reduce){*{transition:none!important;animation:none!important;}}

/* ===== 다크모드: 시스템/브라우저 설정 자동 따라감 (Gradio 가 .dark 클래스 적용) =====
   라이트 규칙은 그대로 두고, .dark 일 때의 색만 덮어써 대비를 살린다. (azure 액센트 유지) */
.dark,html.dark,body.dark,.dark gradio-app,.dark .gradio-container{background:#0e1620!important;}
.dark .gradio-container{
  --color-accent:#00aaff;--color-accent-soft:#10324a;
  --body-background-fill:#0e1620;--background-fill-primary:#18222e;--background-fill-secondary:#0e1620;
  --body-text-color:#e6edf3;--body-text-color-subdued:#93a4b3;
  --block-background-fill:#18222e;--block-border-color:#28333f;
  --block-label-text-color:#93a4b3;--block-title-text-color:#e6edf3;
  --input-background-fill:#131d27;--input-border-color:#2b3a48;--input-border-color-focus:#00aaff;
}
.dark .app-head .name{color:#e6edf3;}
.dark .app-head .sub{color:#93a4b3;}
.dark .card{background:#18222e!important;border-color:#28333f!important;
  box-shadow:0 1px 2px rgba(0,0,0,.30),0 10px 28px rgba(0,0,0,.40)!important;}
.dark .gradio-container label span{color:#c4d2dd!important;}
.dark .stats p{color:#8fa0ad!important;}
.dark .hint p{color:#93a4b3!important;}
.dark .status-ok{color:#e6edf3;background:#0c2230;border-color:#1b4a63;}
.dark .status-ok code{background:#0e1925;border-color:#284a5f;color:#5cc5ff;}
.dark .stat-list{color:#93a4b3;}
.dark .stat-list code{background:#0e1925;border-color:#284050;color:#5cc5ff;}
.dark .recent b{color:#93a4b3;}
.dark .preview-audio{border-color:#28333f!important;}
"""


def on_lang_change(lang_label, mix_on_val):
    """언어 바뀌면 목소리 1·2 드롭다운 갱신 + 언어별 지원 기능 반영.

    - 목소리 섞기: Kokoro 언어만 → 아니면 체크박스·믹스 행 숨김
    - 고품질(Chatterbox) 모드: 속도 슬라이더 대신 감정 강도 슬라이더 표시"""
    info = core.LANGS[lang_label]
    code = info["code"]
    voices = core.voices_for(code)
    can_mix = core.supports_mix(code)
    is_cb = core.is_chatterbox(code)
    slot_upd = [gr.update(choices=voices, value=None) for _ in range(4)]  # 화자 슬롯도 언어 따라
    return (gr.update(choices=voices, value=info["default_voice"]),
            gr.update(choices=voices, value=_second_voice(voices)),
            gr.update(visible=can_mix),
            gr.update(visible=can_mix and bool(mix_on_val)),
            gr.update(visible=not is_cb),
            gr.update(visible=is_cb),
            *slot_upd)


def update_stats(text, lang_label, speed):
    """대본 글자 수 + 대략적인 예상 길이(실측 chars/sec 기반)."""
    n = len((text or "").strip())
    if n == 0:
        return "글자 수 0"
    code = core.LANGS[lang_label]["code"]
    mult = 1.0 if core.is_chatterbox(code) else (speed or 1.0)   # 고품질 모드는 속도 고정
    cps = CPS.get(code, 13.6) * mult
    sec = n / cps if cps else 0
    note = ""
    if core.is_chatterbox(code):
        note = " · 고품질 모드: 생성에 오디오 길이의 몇 배쯤 걸려요 (GPU에선 훨씬 빠름)"
    return f"글자 수 {n:,} · 예상 길이 약 {sec:.0f}초 (대략){note}"


def apply_replacements(text, rules):
    """'원문=읽을말' 줄 단위 치환을 TTS 전에 적용 (발음 교정)."""
    for line in (rules or "").splitlines():
        if "=" in line:
            a, b = line.split("=", 1)
            if a.strip():
                text = text.replace(a.strip(), b.strip())
    return text


def generate(lang_label, voice, speed, text, files, filename, folder, fmt, mix_on, voice2, mix_ratio,
             add_ts, srt_on, gap_sec, norm_mode, replace_rules, trim_on, scene_split, autosave,
             dlg_on, spk_n1, spk_n2, spk_n3, spk_n4, spk_v1, spk_v2, spk_v3, spk_v4,
             srt_max, emotion, pace, takes, progress=gr.Progress()):
    CANCEL_EVENT.clear()
    code = core.LANGS[lang_label]["code"]
    out_folder = folder or DEFAULT_OUTPUT
    takes_n = int(takes or 1)
    spk_pairs = [(spk_n1, spk_v1), (spk_n2, spk_v2), (spk_n3, spk_v3), (spk_n4, spk_v4)]

    # 마지막 선택을 기억(다음 실행 때 복원)
    save_settings({"lang": lang_label, "voice": voice, "voice2": voice2, "speed": speed,
                   "fmt": fmt, "folder": out_folder, "mix_on": bool(mix_on), "add_ts": bool(add_ts),
                   "srt_on": bool(srt_on), "gap_sec": float(gap_sec or 0.0), "norm_mode": norm_mode,
                   "replace_rules": replace_rules or "", "trim_on": bool(trim_on),
                   "scene_split": bool(scene_split), "autosave": bool(autosave),
                   "dlg_on": bool(dlg_on),
                   "spk": [[(n or "").strip(), v or ""] for n, v in spk_pairs],
                   "srt_max": int(srt_max or 0), "emotion": float(emotion or 0.5),
                   "pace": float(pace or 0.5), "takes": takes_n})

    # 대화 모드 화자 매핑 (슬롯 -> dict). 대화 모드 중엔 목소리 섞기 무시.
    # 고품질 모드도 지원: 참고목소리·기본 목소리를 화자별로 지정할 수 있다.
    vmap = None
    if dlg_on:
        vmap = {}
        for nm, vv in spk_pairs:
            nm = (nm or "").strip()
            if not nm:
                continue
            if nm == core.RESET_NAME:
                raise gr.Error(f"'{core.RESET_NAME}'은 기본 목소리 복귀용 예약어라 "
                               "화자 이름으로 쓸 수 없어요.")
            if not vv:
                raise gr.Error(f"화자 '{nm}'의 목소리를 골라 주세요.")
            vmap[nm] = vv
        vmap = vmap or None
    use_mix = mix_on and core.supports_mix(code) and not vmap

    try:
        voice_arg = core.blend_voices(code, voice, voice2, 1.0 - mix_ratio) if use_mix else voice
    except ValueError as e:
        raise gr.Error(str(e))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def named(base):
        return f"{base}_{stamp}" if add_ts else base

    def synth_one(content):
        audio, sr, segs = core.synthesize_segments(
            apply_replacements(content, replace_rules), code, voice_arg, speed, gap_sec or 0.0,
            voice_map=vmap, emotion=emotion, pace=pace,
            should_stop=CANCEL_EVENT.is_set)
        if trim_on:                          # 가장자리 무음 제거 → 자막 타이밍을 앞 trim 만큼 당김
            audio, lead = core.trim_fade(audio, sr)
            dur = len(audio) / sr
            segs = [(t, max(0.0, s - lead), min(dur, max(0.0, e - lead)))
                    for (t, s, e) in segs if (s - lead) < dur]
        if norm_mode == "방송용 (LUFS)":
            audio = core.normalize_lufs(audio, sr)
        elif norm_mode == "피크":
            audio = core.normalize_peak(audio)
        return audio, sr, segs

    # 자동저장 OFF + 단일 대본(업로드/장면분할/테이크 아님) → 저장하지 않고 미리듣기만.
    #   결과는 메모리(State)에 들고 있다가 [저장] 버튼을 누를 때 폴더에 기록한다.
    if not autosave and not files and not scene_split and takes_n == 1:
        if not (text or "").strip():
            raise gr.Error("대본이 비어 있습니다. 텍스트를 입력해 주세요.")
        try:
            audio, sr, segs = synth_one(text)
        except Exception as e:
            raise gr.Error(str(e))
        gr.Info("생성 완료 — 아직 저장 안 됨 ([저장] 버튼으로 저장)")
        preview_path = core.save_audio(audio, sr, PREVIEW_DIR, "preview", fmt)
        status = ('<div class="status-ok">생성됨 · 아직 저장 안 함 — '
                  '아래 <b>[저장]</b> 버튼을 누르면 폴더에 저장돼요.</div>')
        return str(preview_path), status, [], (audio, sr, segs)

    # 작업 목록: (텍스트소스, 파일여부, 저장이름). 업로드가 있으면 우선(장면분할·테이크 무시).
    if files:
        jobs = [(f, True, Path(f).stem) for f in files]
    elif scene_split:                        # 빈 줄로 장면을 나눠 각각 저장
        blocks = [b.strip() for b in re.split(r"\n\s*\n", text or "") if b.strip()]
        jobs = [(b, False, f"{filename}_{i + 1:02d}") for i, b in enumerate(blocks)] \
            or [(text, False, filename)]
    elif takes_n > 1:                        # 같은 대본을 여러 번 생성해 고르기
        jobs = [(text, False, f"{filename}_t{n}") for n in range(1, takes_n + 1)]
    else:
        jobs = [(text, False, filename)]

    saved, skipped, canceled = [], [], False  # saved: (Path, dur); skipped: (이름, 사유)
    total = len(jobs)
    for i, (src, is_path, base) in enumerate(jobs):
        if CANCEL_EVENT.is_set():
            canceled = True
            break
        if total > 1:
            progress(i / total, desc=f"{i + 1}/{total} 생성 중…")
        try:
            content = Path(src).read_text(encoding="utf-8") if is_path else src
            audio, sr, segs = synth_one(content)
            p = core.save_audio(audio, sr, out_folder, named(base), fmt)
            if srt_on:
                core.write_srt(core.split_segments_for_srt(segs, srt_max), p.with_suffix(".srt"))
            saved.append((p, len(audio) / sr))
        except Exception as e:               # 한 개가 실패해도 나머지는 계속
            skipped.append((base, str(e)))
            if CANCEL_EVENT.is_set():        # 취소로 인한 실패면 나머지도 중단
                canceled = True
                break
    progress(1.0)

    if canceled:
        gr.Info(f"취소됨 — 완료된 {len(saved)}개는 저장돼 있어요")
    elif saved:
        gr.Info(f"생성 완료 — {len(saved)}개 저장")

    if not saved:
        if canceled:
            return None, '<div class="status-ok">취소됨 · 저장된 파일 없음</div>', [], None
        raise gr.Error(skipped[0][1] if (skipped and total == 1)
                       else "생성된 파일이 없습니다. " + " / ".join(f"{b} ({m})" for b, m in skipped))

    paths = [str(p) for p, _ in saved]
    srt_note = " · 자막(.srt) 포함" if srt_on else ""
    cancel_note = " · <b>취소됨</b> (완료분만 저장)" if canceled else ""
    if len(saved) == 1 and not skipped and not canceled:
        p, dur = saved[0]
        # 경로는 gr.HTML 로 렌더되므로 이스케이프 (XSS 방지 + '&' 등 특수문자 표시 안전)
        status = (f'<div class="status-ok">저장 완료 · <code>{html.escape(str(p))}</code>'
                  f' · {dur:.1f}초{srt_note}</div>')
    else:
        msg = f"{len(saved)}개 저장 완료{srt_note}{cancel_note}"
        if skipped:
            msg += f" · {len(skipped)}개 건너뜀"
        shown = "<br>".join(f"<code>{html.escape(str(p))}</code>" for p, _ in saved[:8])
        if len(saved) > 8:
            shown += f"<br>… 외 {len(saved) - 8}개"
        status = f'<div class="status-ok">{msg}</div><div class="stat-list">{shown}</div>'
    return paths[0], status, paths, None


def save_pending(pending, filename, folder, fmt, add_ts, srt_on, srt_max):
    """자동저장 OFF로 만든 '미저장 결과'를 지금 설정대로 폴더에 저장한다.

    pending = (audio_np, sample_rate, segments) 또는 None.
    저장 후 pending 을 비우고(최근 목록 갱신용) 저장 경로를 반환한다."""
    if not pending:
        raise gr.Error("저장할 새 결과가 없어요. 먼저 음성을 생성하세요. "
                       "(자동 저장 ON이면 생성 시 바로 저장됩니다.)")
    audio, sr, segs = pending
    out_folder = folder or DEFAULT_OUTPUT
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{filename}_{stamp}" if add_ts else (filename or "narration")
    try:
        p = core.save_audio(audio, sr, out_folder, base, fmt)
        if srt_on:
            core.write_srt(core.split_segments_for_srt(segs, srt_max), p.with_suffix(".srt"))
    except Exception as e:
        raise gr.Error(str(e))
    srt_note = " · 자막(.srt) 포함" if srt_on else ""
    status = (f'<div class="status-ok">저장 완료 · <code>{html.escape(str(p))}</code>'
              f' · {len(audio) / sr:.1f}초{srt_note}</div>')
    return status, [str(p)], None


def update_recent(just_saved, recent):
    """방금 저장한 파일을 세션 '최근 생성' 목록 맨 앞에 추가 (중복 제거, 최대 10개)."""
    new = [p for p in (just_saved or []) if p]
    combined = new + [p for p in (recent or []) if p not in new]
    combined = combined[:10]
    if not combined:
        return "", combined
    items = "<br>".join(f"<code>{html.escape(p)}</code>" for p in combined)
    md = f'<div class="recent"><b>최근 생성 (이번 세션)</b><div class="stat-list">{items}</div></div>'
    return md, combined


def preview(lang_label, voice, speed, mix_on, voice2, mix_ratio, emotion, pace):
    """선택한 목소리(또는 믹스)로 짧은 샘플을 합성해 메모리로 재생. 파일은 저장하지 않음."""
    code = core.LANGS[lang_label]["code"]
    use_mix = mix_on and core.supports_mix(code)
    try:
        voice_arg = core.blend_voices(code, voice, voice2, 1.0 - mix_ratio) if use_mix else voice
        audio, sr = core.synthesize(PREVIEW_TEXT.get(code, PREVIEW_TEXT["a"]), code, voice_arg,
                                    speed, emotion=emotion, pace=pace)
    except (ValueError, RuntimeError) as e:
        raise gr.Error(str(e))
    # gr.Audio(type="numpy") 는 (sample_rate, 데이터) 튜플을 받음. int16 로 안전하게 변환.
    return sr, (audio * 32767).clip(-32768, 32767).astype("int16")


# --- 저장 폴더 고르기/열기 (로컬 앱이므로 OS 기능 사용) ---

def pick_folder(current):
    """OS 네이티브 '폴더 선택' 창을 띄워 고른 경로를 반환. 취소/실패 시 기존 값 유지.

    Tk 는 별도 프로세스(자체 main 스레드)에서 실행 → 맥/윈 모두 안전."""
    code = (
        "import tkinter as tk, sys\n"
        "from tkinter import filedialog\n"
        "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
        "p = filedialog.askdirectory()\n"
        "sys.stdout.buffer.write((p or '').encode('utf-8'))\n"
    )
    try:
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=300)
        chosen = res.stdout.decode("utf-8", "replace").strip()
        return chosen or (current or DEFAULT_OUTPUT)
    except Exception:
        return current or DEFAULT_OUTPUT


def open_folder(folder):
    """저장 폴더를 탐색기(윈도우)/파인더(맥)로 연다."""
    target = Path(folder or DEFAULT_OUTPUT).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(str(target))  # noqa: B606  (윈도우 전용)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target)])
        else:
            subprocess.run(["xdg-open", str(target)])
    except Exception as e:
        raise gr.Error(f"폴더를 열 수 없습니다: {e}")


with gr.Blocks(title="외국어 영상 TTS") as demo:
    gr.HTML(HEADER_HTML)

    with gr.Accordion("도움말 — 처음이세요? (사용법 펼치기)", open=False):
        gr.Markdown(
            "1. **언어·목소리·속도**를 고르고, **미리듣기**로 목소리를 들어볼 수 있어요.\n"
            "2. **대본**에 읽을 내용을 붙여넣습니다. (영상이 여러 개면 ‘파일로 만들기’로 .txt 여러 개를 한 번에)\n"
            "3. **포맷**(영상 편집엔 WAV, 공유엔 MP3)과 **저장 폴더**를 고릅니다.\n"
            "4. **[음성 생성]** → 폴더에 저장되고 바로 재생·다운로드됩니다.\n\n"
            "- **목소리 섞기**: 두 목소리를 비율로 혼합해 새 음색 (한국어는 미지원).\n"
            "- **대화 모드**: 화자 슬롯에 이름·목소리를 넣고(또는 **[대본에서 화자 자동 인식]**) "
            "대본 줄 앞에 `이름:` — 한 번 쓰면 **다음 화자 표시까지 유지**되고, `기본:`으로 "
            "기본 목소리에 복귀해요.\n"
            "- **쉼 태그**: 대본 속 `[쉼:1.5]` 자리에 정확히 1.5초 무음. 줄 전체가 태그뿐이면 자막 없는 쉼.\n"
            "- **자막(.srt)**: 음성과 함께 자막 파일 저장. ‘한 줄 최대 글자 수’로 긴 자막 자동 나누기.\n"
            "- **음량 정규화**: 클립마다 볼륨을 비슷하게 (방송용 = 유튜브 권장 음량).\n"
            "- **추가 옵션**: 잘못 읽는 단어 교정(발음 교정), 문단 사이 쉼 넣기.\n"
            "- **장면별로 나눠 저장**: 대본을 빈 줄로 나눠 장면마다 따로 파일로.\n"
            "- **한국어**: 첫 생성 때 모델을 자동 다운로드해요(인터넷 1회). 속도는 0.7 미만이면 0.7로 조정됩니다.\n"
            "- **고품질·감정 모드**: 더 자연스러운 목소리 + **감정 강도**(차분~극적)와 "
            "**말 페이스**(느긋~빠릿) 슬라이더로 직접 조절. 감정을 올리면 말이 빨라지는 "
            "경향이 있으니 페이스를 낮춰 균형을 잡으면 좋아요. "
            "먼저 폴더의 `SETUP-고품질모드` 를 한 번 실행하세요(첫 사용 시 모델 ~3GB 다운로드). "
            "생성이 느린 대신 품질이 높고(그래픽카드 있으면 빠름), 목소리 섞기만 지원하지 않아요 "
            "(대화 모드는 참고 목소리들로 가능).\n"
            "- **내 목소리 쓰기(고품질 모드)**: `참고목소리` 폴더에 10~20초 녹음 파일(wav/mp3)을 "
            "넣고 **[목소리 새로고침]** 을 누르면 파일 이름이 목소리 목록에 나타나요 — 그 목소리를 "
            "복제해 읽습니다. 반드시 본인·동업자 등 **권리 있는 목소리만** 사용하세요.",
            elem_classes="hint")

    with gr.Group(elem_classes="card"):
        with gr.Row():
            lang = gr.Dropdown(LANG_LABELS, value=INIT_LANG, label="언어")
            voice = gr.Dropdown(INIT_VOICES, value=INIT_VOICE, label="목소리")
            speed = gr.Slider(0.5, 2.0, value=INIT_SPEED, step=0.05, label="속도",
                              info="1.0 = 보통", visible=not INIT_IS_CB)
        with gr.Row(visible=INIT_IS_CB) as hq_row:   # 고품질 모드 전용 조절 (전용 행 = 설명 안 깨짐)
            emotion = gr.Slider(0.0, 1.0, value=INIT_EMOTION, step=0.05, label="감정 강도",
                                info="0.3 차분 · 0.5 보통 · 0.7 극적")
            pace = gr.Slider(0.2, 0.8, value=INIT_PACE, step=0.05, label="말 페이스",
                             info="낮음 느긋 · 0.5 보통 · 높음 빠릿")
        mix_on = gr.Checkbox(value=INIT_MIX, visible=INIT_CAN_MIX,
                             label="목소리 섞기 — 두 목소리를 비율로 혼합 (같은 언어끼리)")
        with gr.Row(visible=INIT_MIX and INIT_CAN_MIX) as mix_row:
            voice2 = gr.Dropdown(INIT_VOICES, value=INIT_VOICE2, label="목소리 2")
            mix_ratio = gr.Slider(0.0, 1.0, value=0.5, step=0.05, label="섞는 비율",
                                  info="왼쪽 = 목소리 1 · 오른쪽 = 목소리 2")
        with gr.Row():
            preview_btn = gr.Button("미리듣기", size="sm", scale=0, min_width=120,
                                    elem_classes="preview-btn")
            refresh_btn = gr.Button("목소리 새로고침", size="sm", scale=0, min_width=140)
        preview_audio = gr.Audio(label="미리듣기 (선택한 목소리 샘플)", type="numpy",
                                 autoplay=True, elem_classes=["audio-out", "preview-audio"])

    with gr.Group(elem_classes="card"):
        text = gr.Textbox(lines=6, label="대본",
                          placeholder="여기에 대본을 붙여넣으세요. 문장·문단마다 줄바꿈하면 더 자연스럽습니다.\n"
                                      "원하는 곳에 [쉼:1.5] 를 넣으면 그 자리에서 1.5초 쉬어요.")
        stats = gr.Markdown("글자 수 0", elem_classes="stats")
        dlg_on = gr.Checkbox(value=INIT_DLG, label="대화 모드 — 줄 앞 ‘이름:’ 표시로 화자별 목소리")
        with gr.Column(visible=INIT_DLG) as dlg_col:
            gr.Markdown("대본 줄 앞에 **이름:** 을 쓰면 그 화자가 **다음 화자 표시까지 유지**돼요 "
                        "(긴 대사는 이름 한 번만). **기본:** 이라고 쓰면 기본 목소리(내레이션)로 "
                        "돌아옵니다. 자막에는 이름이 빠지고, 대화 모드 중 목소리 섞기는 무시돼요.",
                        elem_classes="hint")
            spk_names, spk_voices, spk_btns = [], [], []
            for _si in range(4):
                with gr.Row():
                    _n = gr.Textbox(value=INIT_SPK[_si][0], label=f"화자 {_si + 1} 이름",
                                    placeholder="예: 민수", scale=2)
                    _v = gr.Dropdown(INIT_VOICES, value=INIT_SPK[_si][1],
                                     label="목소리", scale=3)
                    _b = gr.Button("듣기", size="sm", scale=0, min_width=64)
                    spk_names.append(_n); spk_voices.append(_v); spk_btns.append(_b)
            detect_btn = gr.Button("대본에서 화자 자동 인식 — ‘이름:’ 을 찾아 빈 슬롯 채우기",
                                   size="sm")
        with gr.Accordion("파일로 만들기 — .txt 여러 개 올리면 한 번에 (선택)", open=False):
            gr.Markdown("파일을 올리면 위 대본 대신 **각 파일 내용**으로 만들고, **각 파일 이름**으로 저장됩니다 "
                        "(아래 ‘파일 이름’ 칸은 무시).", elem_classes="hint")
            upload = gr.File(file_count="multiple", file_types=[".txt"], elem_classes="upload",
                             label="텍스트 파일(.txt) — 여러 개 선택 가능")
        with gr.Accordion("추가 옵션 — 발음 교정 · 문단 사이 쉼 (선택)", open=False):
            replace_rules = gr.Textbox(value=INIT_REPLACE, lines=3,
                                       label="발음 교정 (한 줄에 하나: 원문=읽을말)",
                                       info="읽을말은 그 목소리의 언어로 적으세요 — 영어=영어 철자, "
                                            "일본어=카나. 한글로 적으면 안 읽혀요. "
                                            "(짧은 글자는 다른 단어 속까지 바뀔 수 있어요)",
                                       placeholder="예) 영어 목소리:  AI=ay eye\n"
                                                   "예) 영어 목소리:  2024=twenty twenty four\n"
                                                   "예) 일본어 목소리:  AI=エーアイ")
            gap_sec = gr.Slider(0.0, 2.0, value=INIT_GAP, step=0.1, label="문단(줄) 사이 쉼",
                                info="줄바꿈마다 넣을 무음 길이(초). 0 = 없음")
            takes = gr.Slider(1, 5, value=INIT_TAKES, step=1, label="테이크 수",
                              info="같은 대본을 여러 번 생성해 제일 좋은 것 고르기 — _t1, _t2… 로 "
                                   "저장돼요 (단일 대본일 때만, 고품질 모드에서 특히 유용)")

    with gr.Group(elem_classes="card"):
        with gr.Row():
            filename = gr.Textbox(value="narration", label="파일 이름 (확장자 자동)")
            fmt = gr.Dropdown(FORMAT_LABELS, value=INIT_FMT, label="포맷 (WAV = 편집용 / MP3 = 공유)")
        autosave = gr.Checkbox(value=INIT_AUTOSAVE,
                               label="생성 시 자동 저장 (끄면 아래 [저장] 버튼으로 직접 저장)")
        add_ts = gr.Checkbox(value=INIT_TS, label="파일 이름에 날짜·시간 자동 추가 (덮어쓰기 방지)")
        with gr.Row():
            srt_on = gr.Checkbox(value=INIT_SRT, label="자막(.srt)도 같이 저장")
            trim_on = gr.Checkbox(value=INIT_TRIM, label="무음 다듬기 + 페이드 (앞뒤 정리)")
        srt_max = gr.Slider(0, 60, value=INIT_SRT_MAX, step=1,
                            label="자막 한 줄 최대 글자 수 (0 = 제한 없음)",
                            info="긴 자막을 여러 개로 나눠요 — 영어 42 / 한국어·일본어 20~24 권장")
        scene_split = gr.Checkbox(value=INIT_SCENE,
                                  label="장면별로 나눠 저장 (빈 줄로 장면 구분 → 문단마다 파일)")
        norm_mode = gr.Radio(NORM_MODES, value=INIT_NORM, label="음량 정규화",
                             info="피크 = 최대치 맞춤 / 방송용 = 유튜브 등 체감 음량(-14 LUFS)")
        folder = gr.Textbox(value=INIT_FOLDER, label="저장 폴더",
                            info="아래 버튼으로 고르거나, 경로를 직접 입력해도 됩니다.")
        with gr.Row(elem_classes="folder-tools"):
            browse_btn = gr.Button("폴더 찾아보기…", size="sm")
            desktop_btn = gr.Button("바탕화면", size="sm")
            downloads_btn = gr.Button("다운로드", size="sm")
            default_btn = gr.Button("기본 폴더", size="sm")

    with gr.Row():
        btn = gr.Button("음성 생성", variant="primary", elem_classes="generate-btn", scale=5)
        cancel_btn = gr.Button("취소", size="lg", scale=1)
    audio_out = gr.Audio(label="결과 (재생 / 다운로드)", type="filepath", elem_classes="audio-out")
    status = gr.HTML(elem_id="status")
    with gr.Row(elem_classes="folder-tools"):
        save_btn = gr.Button("저장", size="sm")
        open_btn = gr.Button("저장 폴더 열기", size="sm")
    recent_html = gr.HTML(elem_id="recent")
    last_saved = gr.State()
    recent_state = gr.State([])
    pending_state = gr.State()      # 자동저장 OFF로 만든 미저장 결과 (audio, sr, segs)

    lang.change(on_lang_change, inputs=[lang, mix_on],
                outputs=[voice, voice2, mix_on, mix_row, speed, hq_row] + spk_voices)
    lang.change(update_stats, inputs=[text, lang, speed], outputs=stats)
    text.change(update_stats, inputs=[text, lang, speed], outputs=stats)
    speed.change(update_stats, inputs=[text, lang, speed], outputs=stats)
    mix_on.change(lambda on, lang_label: gr.update(
                      visible=on and core.supports_mix(core.LANGS[lang_label]["code"])),
                  inputs=[mix_on, lang], outputs=mix_row)
    dlg_on.change(lambda on: gr.update(visible=on), inputs=dlg_on, outputs=dlg_col)

    def refresh_voices(lang_label, cur_voice, cur_voice2, *slot_vals):
        """참고목소리 폴더를 다시 읽어 모든 목소리 드롭다운 갱신 (선택 값은 가능하면 유지)."""
        voices = core.voices_for(core.LANGS[lang_label]["code"])
        keep = cur_voice if cur_voice in voices else core.LANGS[lang_label]["default_voice"]
        keep2 = cur_voice2 if cur_voice2 in voices else _second_voice(voices)
        slot_upd = [gr.update(choices=voices, value=(v if v in voices else None))
                    for v in slot_vals]
        return [gr.update(choices=voices, value=keep),
                gr.update(choices=voices, value=keep2)] + slot_upd

    refresh_btn.click(refresh_voices, inputs=[lang, voice, voice2] + spk_voices,
                      outputs=[voice, voice2] + spk_voices)

    def slot_preview(lang_label, slot_voice, speed_val, emotion_val, pace_val):
        """화자 슬롯의 목소리를 짧은 샘플로 미리듣기."""
        if not slot_voice:
            raise gr.Error("이 화자의 목소리를 먼저 골라 주세요.")
        return preview(lang_label, slot_voice, speed_val, False, None, 0.5,
                       emotion_val, pace_val)

    for _b, _v in zip(spk_btns, spk_voices):
        _b.click(slot_preview, inputs=[lang, _v, speed, emotion, pace],
                 outputs=preview_audio)

    _NAME_PREFIX = re.compile(r"^\s*([^\s:：][^:：]{0,19}?)\s*[:：]")

    def detect_speakers(script, lang_label, *slots):
        """대본에서 '이름:' 접두사를 찾아 빈 슬롯에 이름을 채우고, 목소리도 자동 제안."""
        names = [(_n or "").strip() for _n in slots[0:4]]
        voices_sel = list(slots[4:8])
        seen = {n for n in names if n}
        found = []
        for line in (script or "").splitlines():
            m = _NAME_PREFIX.match(line)
            if not m:
                continue
            nm = m.group(1).strip()
            if nm and nm != core.RESET_NAME and nm not in seen:
                seen.add(nm)
                found.append(nm)
        all_voices = core.voices_for(core.LANGS[lang_label]["code"])
        avail = [v for v in all_voices if v not in {v for v in voices_sel if v}]
        out, fi = [], 0
        for i in range(4):
            nm, vv = names[i], voices_sel[i]
            if not nm and fi < len(found):
                nm = found[fi]
                fi += 1
                if not vv and avail:
                    vv = avail.pop(0)
            out.append(gr.update(value=nm))
            out.append(gr.update(value=vv))
        return out

    detect_btn.click(detect_speakers, inputs=[text, lang] + spk_names + spk_voices,
                     outputs=[x for pair in zip(spk_names, spk_voices) for x in pair])
    preview_btn.click(preview, inputs=[lang, voice, speed, mix_on, voice2, mix_ratio, emotion, pace],
                      outputs=preview_audio)
    browse_btn.click(pick_folder, inputs=folder, outputs=folder)
    desktop_btn.click(lambda: str(Path.home() / "Desktop"), outputs=folder)
    downloads_btn.click(lambda: str(Path.home() / "Downloads"), outputs=folder)
    default_btn.click(lambda: DEFAULT_OUTPUT, outputs=folder)
    open_btn.click(open_folder, inputs=folder, outputs=[])
    btn.click(generate,
              inputs=[lang, voice, speed, text, upload, filename, folder, fmt, mix_on, voice2,
                      mix_ratio, add_ts, srt_on, gap_sec, norm_mode, replace_rules, trim_on, scene_split,
                      autosave, dlg_on] + spk_names + spk_voices + [srt_max, emotion, pace, takes],
              outputs=[audio_out, status, last_saved, pending_state],
              show_progress_on=audio_out).then(
              update_recent, inputs=[last_saved, recent_state], outputs=[recent_html, recent_state])
    save_btn.click(save_pending,
                   inputs=[pending_state, filename, folder, fmt, add_ts, srt_on, srt_max],
                   outputs=[status, last_saved, pending_state]).then(
                   update_recent, inputs=[last_saved, recent_state], outputs=[recent_html, recent_state])

    def request_cancel():
        """생성 취소 요청 — 진행 중인 줄까지만 만들고 멈춘다 (완료분은 저장 유지)."""
        CANCEL_EVENT.set()
        gr.Info("취소 요청됨 — 진행 중인 부분까지만 만들고 멈춥니다")

    cancel_btn.click(request_cancel, inputs=[], outputs=[])


if __name__ == "__main__":
    # Gradio 6.0+: theme/css/head 는 launch() 로 전달.
    # allowed_paths: 사용자가 지정한 폴더(보통 홈 디렉터리 하위)의 파일을 브라우저에서 재생/다운로드 허용
    demo.launch(inbrowser=True, allowed_paths=[str(Path.home()), DEFAULT_OUTPUT, PREVIEW_DIR],
                theme=gr.themes.Base(), css=CSS, head=HEAD)
