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
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import gradio as gr

import kokoro_core as core

DEFAULT_OUTPUT = str((Path(__file__).resolve().parent / "output").resolve())
LANG_LABELS = list(core.LANGS.keys())
FIRST_LANG = LANG_LABELS[0]
FORMAT_LABELS = list(core.FORMATS.keys())

# 실측 기반 대략치 (chars/sec, 속도 1.0): 영어 13.6 / 일본어 5.6
CPS = {"a": 13.6, "b": 13.6, "j": 5.6}

# 목소리 미리듣기용 짧은 샘플 문장 (언어별)
PREVIEW_TEXT = {
    "a": "This is a preview of the selected voice.",
    "b": "This is a preview of the selected voice.",
    "j": "これは、選んだ声のプレビューです。",
}

SETTINGS_PATH = Path.home() / ".foreign-video-tts.json"


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
INIT_NORM = bool(_s.get("normalize_on", False))
try:
    INIT_GAP = float(_s.get("gap_sec", 0.0))
except (TypeError, ValueError):
    INIT_GAP = 0.0
INIT_GAP = INIT_GAP if 0.0 <= INIT_GAP <= 2.0 else 0.0
INIT_REPLACE = _s.get("replace_rules", "") or ""

# Pretendard 웹폰트 (인터넷 필요; 없으면 시스템 폰트로 자연 폴백)
HEAD = (
    '<link rel="stylesheet" '
    'href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@latest/dist/web/static/pretendard.css">'
)

HEADER_HTML = """
<div class="app-head">
  <div class="bar"></div>
  <div class="brand"><span class="mark"></span><span class="name">외국어 영상 TTS</span></div>
  <p class="sub">Kokoro 기반 내레이션 음성 생성 · 일본어와 영어</p>
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
"""


def on_lang_change(lang_label):
    """언어 바뀌면 목소리 1·2 드롭다운을 해당 언어 목록으로 함께 갱신."""
    info = core.LANGS[lang_label]
    voices = core.voices_for(info["code"])
    return (gr.update(choices=voices, value=info["default_voice"]),
            gr.update(choices=voices, value=_second_voice(voices)))


def update_stats(text, lang_label, speed):
    """대본 글자 수 + 대략적인 예상 길이(실측 chars/sec 기반)."""
    n = len((text or "").strip())
    if n == 0:
        return "글자 수 0"
    code = core.LANGS[lang_label]["code"]
    cps = CPS.get(code, 13.6) * (speed or 1.0)
    sec = n / cps if cps else 0
    return f"글자 수 {n:,} · 예상 길이 약 {sec:.0f}초 (대략)"


def apply_replacements(text, rules):
    """'원문=읽을말' 줄 단위 치환을 TTS 전에 적용 (발음 교정)."""
    for line in (rules or "").splitlines():
        if "=" in line:
            a, b = line.split("=", 1)
            if a.strip():
                text = text.replace(a.strip(), b.strip())
    return text


def generate(lang_label, voice, speed, text, files, filename, folder, fmt, mix_on, voice2, mix_ratio,
             add_ts, srt_on, gap_sec, normalize_on, replace_rules, progress=gr.Progress()):
    code = core.LANGS[lang_label]["code"]
    out_folder = folder or DEFAULT_OUTPUT

    # 마지막 선택을 기억(다음 실행 때 복원)
    save_settings({"lang": lang_label, "voice": voice, "voice2": voice2, "speed": speed,
                   "fmt": fmt, "folder": out_folder, "mix_on": bool(mix_on), "add_ts": bool(add_ts),
                   "srt_on": bool(srt_on), "gap_sec": float(gap_sec or 0.0),
                   "normalize_on": bool(normalize_on), "replace_rules": replace_rules or ""})

    try:
        voice_arg = core.blend_voices(code, voice, voice2, 1.0 - mix_ratio) if mix_on else voice
    except ValueError as e:
        raise gr.Error(str(e))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def named(base):
        return f"{base}_{stamp}" if add_ts else base

    def synth_one(content):
        audio, sr, segs = core.synthesize_segments(
            apply_replacements(content, replace_rules), code, voice_arg, speed, gap_sec or 0.0)
        if normalize_on:
            audio = core.normalize_peak(audio)
        return audio, sr, segs

    if files:  # --- 배치: 업로드한 .txt 파일마다 1개씩 (파일 이름으로 저장) ---
        saved, skipped = [], []
        total = len(files)
        for i, f in enumerate(files):
            progress(i / total, desc=f"{i + 1}/{total} 생성 중…")
            try:
                audio, sr, segs = synth_one(Path(f).read_text(encoding="utf-8"))
                p = core.save_audio(audio, sr, out_folder, named(Path(f).stem), fmt)
                if srt_on:
                    core.write_srt(segs, p.with_suffix(".srt"))
                saved.append(p)
            except Exception as e:  # 한 파일이 실패해도 나머지는 계속 (tts.py 와 동일한 회복성)
                skipped.append(f"{Path(f).name} ({e})")
        progress(1.0)
        if not saved:
            raise gr.Error("생성된 파일이 없습니다. " + (" / ".join(skipped) if skipped else ""))
        msg = f"{len(saved)}개 저장 완료" + (" (자막 포함)" if srt_on else "")
        if skipped:
            msg += f" · {len(skipped)}개 건너뜀"
        shown = "<br>".join(f"<code>{html.escape(str(p))}</code>" for p in saved[:8])
        if len(saved) > 8:
            shown += f"<br>… 외 {len(saved) - 8}개"
        status = f'<div class="status-ok">{msg}</div><div class="stat-list">{shown}</div>'
        return str(saved[0]), status, [str(p) for p in saved]

    # --- 단일: 대본 텍스트로 1개 ---
    progress(0.3, desc="생성 중…")
    try:
        audio, sr, segs = synth_one(text)
    except ValueError as e:
        raise gr.Error(str(e))
    path = core.save_audio(audio, sr, out_folder, named(filename), fmt)
    if srt_on:
        core.write_srt(segs, path.with_suffix(".srt"))
    progress(1.0)
    dur = len(audio) / sr
    extra = " · 자막(.srt) 포함" if srt_on else ""
    # 경로는 gr.HTML 로 렌더되므로 이스케이프 (XSS 방지 + '&' 등 특수문자 표시 안전)
    status = f'<div class="status-ok">저장 완료 · <code>{html.escape(str(path))}</code> · {dur:.1f}초{extra}</div>'
    return str(path), status, [str(path)]


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


def preview(lang_label, voice, speed, mix_on, voice2, mix_ratio):
    """선택한 목소리(또는 믹스)로 짧은 샘플을 합성해 메모리로 재생. 파일은 저장하지 않음."""
    code = core.LANGS[lang_label]["code"]
    try:
        voice_arg = core.blend_voices(code, voice, voice2, 1.0 - mix_ratio) if mix_on else voice
        audio, sr = core.synthesize(PREVIEW_TEXT.get(code, PREVIEW_TEXT["a"]), code, voice_arg, speed)
    except ValueError as e:
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

    with gr.Group(elem_classes="card"):
        with gr.Row():
            lang = gr.Dropdown(LANG_LABELS, value=INIT_LANG, label="언어")
            voice = gr.Dropdown(INIT_VOICES, value=INIT_VOICE, label="목소리")
            speed = gr.Slider(0.5, 2.0, value=INIT_SPEED, step=0.05, label="속도", info="1.0 = 보통")
        mix_on = gr.Checkbox(value=INIT_MIX, label="목소리 섞기 — 두 목소리를 비율로 혼합 (같은 언어끼리)")
        with gr.Row(visible=INIT_MIX) as mix_row:
            voice2 = gr.Dropdown(INIT_VOICES, value=INIT_VOICE2, label="목소리 2")
            mix_ratio = gr.Slider(0.0, 1.0, value=0.5, step=0.05, label="섞는 비율",
                                  info="왼쪽 = 목소리 1 · 오른쪽 = 목소리 2")
        with gr.Row():
            preview_btn = gr.Button("미리듣기", size="sm", scale=0, min_width=120,
                                    elem_classes="preview-btn")
        preview_audio = gr.Audio(label="미리듣기 (선택한 목소리 샘플)", type="numpy",
                                 autoplay=True, elem_classes=["audio-out", "preview-audio"])

    with gr.Group(elem_classes="card"):
        text = gr.Textbox(lines=6, label="대본",
                          placeholder="여기에 대본을 붙여넣으세요. 문장·문단마다 줄바꿈하면 더 자연스럽습니다.")
        stats = gr.Markdown("글자 수 0", elem_classes="stats")
        with gr.Accordion("파일로 만들기 — .txt 여러 개 올리면 한 번에 (선택)", open=False):
            gr.Markdown("파일을 올리면 위 대본 대신 **각 파일 내용**으로 만들고, **각 파일 이름**으로 저장됩니다 "
                        "(아래 ‘파일 이름’ 칸은 무시).", elem_classes="hint")
            upload = gr.File(file_count="multiple", file_types=[".txt"], elem_classes="upload",
                             label="텍스트 파일(.txt) — 여러 개 선택 가능")
        with gr.Accordion("추가 옵션 — 발음 교정 · 문단 사이 쉼 (선택)", open=False):
            replace_rules = gr.Textbox(value=INIT_REPLACE, lines=3,
                                       label="발음 교정 (한 줄에 하나: 원문=읽을말)",
                                       placeholder="예) AI=에이아이\n예) 2024=이천이십사년")
            gap_sec = gr.Slider(0.0, 2.0, value=INIT_GAP, step=0.1, label="문단(줄) 사이 쉼",
                                info="줄바꿈마다 넣을 무음 길이(초). 0 = 없음")

    with gr.Group(elem_classes="card"):
        with gr.Row():
            filename = gr.Textbox(value="narration", label="파일 이름 (확장자 자동)")
            fmt = gr.Dropdown(FORMAT_LABELS, value=INIT_FMT, label="포맷 (WAV = 편집용 / MP3 = 공유)")
        add_ts = gr.Checkbox(value=INIT_TS, label="파일 이름에 날짜·시간 자동 추가 (덮어쓰기 방지)")
        with gr.Row():
            srt_on = gr.Checkbox(value=INIT_SRT, label="자막(.srt)도 같이 저장")
            normalize_on = gr.Checkbox(value=INIT_NORM, label="음량 맞추기 (피크 기준)")
        folder = gr.Textbox(value=INIT_FOLDER, label="저장 폴더",
                            info="아래 버튼으로 고르거나, 경로를 직접 입력해도 됩니다.")
        with gr.Row(elem_classes="folder-tools"):
            browse_btn = gr.Button("폴더 찾아보기…", size="sm")
            desktop_btn = gr.Button("바탕화면", size="sm")
            downloads_btn = gr.Button("다운로드", size="sm")
            default_btn = gr.Button("기본 폴더", size="sm")

    btn = gr.Button("음성 생성", variant="primary", elem_classes="generate-btn")
    audio_out = gr.Audio(label="결과 (재생 / 다운로드)", type="filepath", elem_classes="audio-out")
    status = gr.HTML(elem_id="status")
    with gr.Row(elem_classes="folder-tools"):
        open_btn = gr.Button("저장 폴더 열기", size="sm")
    recent_html = gr.HTML(elem_id="recent")
    last_saved = gr.State()
    recent_state = gr.State([])

    lang.change(on_lang_change, inputs=lang, outputs=[voice, voice2])
    lang.change(update_stats, inputs=[text, lang, speed], outputs=stats)
    text.change(update_stats, inputs=[text, lang, speed], outputs=stats)
    speed.change(update_stats, inputs=[text, lang, speed], outputs=stats)
    mix_on.change(lambda on: gr.update(visible=on), inputs=mix_on, outputs=mix_row)
    preview_btn.click(preview, inputs=[lang, voice, speed, mix_on, voice2, mix_ratio], outputs=preview_audio)
    browse_btn.click(pick_folder, inputs=folder, outputs=folder)
    desktop_btn.click(lambda: str(Path.home() / "Desktop"), outputs=folder)
    downloads_btn.click(lambda: str(Path.home() / "Downloads"), outputs=folder)
    default_btn.click(lambda: DEFAULT_OUTPUT, outputs=folder)
    open_btn.click(open_folder, inputs=folder, outputs=[])
    btn.click(generate,
              inputs=[lang, voice, speed, text, upload, filename, folder, fmt, mix_on, voice2,
                      mix_ratio, add_ts, srt_on, gap_sec, normalize_on, replace_rules],
              outputs=[audio_out, status, last_saved]).then(
              update_recent, inputs=[last_saved, recent_state], outputs=[recent_html, recent_state])


if __name__ == "__main__":
    # Gradio 6.0+: theme/css/head 는 launch() 로 전달.
    # allowed_paths: 사용자가 지정한 폴더(보통 홈 디렉터리 하위)의 파일을 브라우저에서 재생/다운로드 허용
    demo.launch(inbrowser=True, allowed_paths=[str(Path.home()), DEFAULT_OUTPUT],
                theme=gr.themes.Base(), css=CSS, head=HEAD)
