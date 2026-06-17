"""
외국어 영상 TTS — 웹 UI (Gradio)
=================================
브라우저에서 언어·목소리·속도를 고르고 대본을 넣으면 음성을 만들어
원하는 폴더에 원하는 이름·포맷(WAV/MP3/FLAC/OGG)으로 저장한다.
목소리 두 개를 비율로 섞을 수도 있다. (음성 생성은 kokoro_core 공유)

디자인: Pretendard 글꼴 + azure(#00aaff) 액센트.
실행:  python app.py   (브라우저가 자동으로 열립니다)
"""

import html
import os
import subprocess
import sys
from pathlib import Path

import gradio as gr

import kokoro_core as core

DEFAULT_OUTPUT = str((Path(__file__).resolve().parent / "output").resolve())
LANG_LABELS = list(core.LANGS.keys())
FIRST_LANG = LANG_LABELS[0]
FIRST_CODE = core.LANGS[FIRST_LANG]["code"]
FIRST_VOICES = core.voices_for(FIRST_CODE)
FORMAT_LABELS = list(core.FORMATS.keys())

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
  max-width:860px!important;margin:0 auto!important;padding:0 20px 56px!important;background:#f4f8fb;
}
body,.gradio-container{font-family:'Pretendard','Apple SD Gothic Neo',system-ui,-apple-system,sans-serif!important;background:#f4f8fb;}
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

.gradio-container input:focus,.gradio-container textarea:focus,.gradio-container select:focus{
  border-color:#00aaff!important;box-shadow:0 0 0 3px rgba(0,170,255,.16)!important;}

/* 결과(오디오) 영역의 장식 음표만 숨김 — 재생/다운로드 컨트롤·업로드 아이콘은 유지 */
.audio-out label svg{display:none!important;}
.audio-out .empty svg{display:none!important;}

/* 폴더 빠른 선택/열기 버튼 */
.folder-tools{gap:8px!important;}
.folder-tools button{font-weight:600!important;}

@media (prefers-reduced-motion: reduce){*{transition:none!important;animation:none!important;}}
"""


def _second_voice(voices):
    """기본 '목소리 2'는 '목소리 1' 기본값과 겹치지 않게 두 번째 항목으로."""
    return voices[1] if len(voices) > 1 else voices[0]


def on_lang_change(lang_label):
    """언어 바뀌면 목소리 1·2 드롭다운을 해당 언어 목록으로 함께 갱신."""
    info = core.LANGS[lang_label]
    voices = core.voices_for(info["code"])
    return (gr.update(choices=voices, value=info["default_voice"]),
            gr.update(choices=voices, value=_second_voice(voices)))


def generate(lang_label, voice, speed, text, uploaded_file, filename, folder,
             fmt, mix_on, voice2, mix_ratio):
    # 업로드한 .txt가 있으면 그것을, 없으면 텍스트박스 내용을 사용
    content = text
    if uploaded_file:
        content = Path(uploaded_file).read_text(encoding="utf-8")

    code = core.LANGS[lang_label]["code"]
    try:
        if mix_on:
            # 슬라이더 0=완전 목소리1, 1=완전 목소리2 → ratio(목소리1 비중)=1-슬라이더
            voice_arg = core.blend_voices(code, voice, voice2, 1.0 - mix_ratio)
        else:
            voice_arg = voice
        audio, sr = core.synthesize(content, code, voice_arg, speed)
    except ValueError as e:
        raise gr.Error(str(e))

    path = core.save_audio(audio, sr, folder or DEFAULT_OUTPUT, filename, fmt)
    dur = len(audio) / sr
    # 경로는 gr.HTML 로 렌더되므로 이스케이프 (XSS 방지 + '&' 등 특수문자 표시 안전)
    status = f'<div class="status-ok">저장 완료 · <code>{html.escape(str(path))}</code> · {dur:.1f}초</div>'
    return str(path), status


# --- 저장 폴더 고르기/열기 (로컬 앱이므로 OS 기능 사용) ---

def pick_folder(current):
    """OS 네이티브 '폴더 선택' 창을 띄워 고른 경로를 반환. 취소하면 기존 값 유지.

    Tk 는 별도 프로세스(자체 main 스레드)에서 실행 → 맥/윈 모두 안전.
    Tk 가 없는 환경이면 조용히 기존 값을 유지(아래 입력칸 직접 입력으로 폴백)."""
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
            lang = gr.Dropdown(LANG_LABELS, value=FIRST_LANG, label="언어")
            voice = gr.Dropdown(FIRST_VOICES,
                                value=core.LANGS[FIRST_LANG]["default_voice"], label="목소리")
            speed = gr.Slider(0.5, 2.0, value=1.0, step=0.05, label="속도", info="1.0 = 보통")
        mix_on = gr.Checkbox(value=False, label="목소리 섞기 — 두 목소리를 비율로 혼합 (같은 언어끼리)")
        with gr.Row(visible=False) as mix_row:
            voice2 = gr.Dropdown(FIRST_VOICES, value=_second_voice(FIRST_VOICES), label="목소리 2")
            mix_ratio = gr.Slider(0.0, 1.0, value=0.5, step=0.05, label="섞는 비율",
                                  info="왼쪽 = 목소리 1 · 오른쪽 = 목소리 2")

    with gr.Group(elem_classes="card"):
        text = gr.Textbox(lines=6, label="대본",
                          placeholder="여기에 대본을 붙여넣으세요. 문장·문단마다 줄바꿈하면 더 자연스럽습니다.")
        upload = gr.File(file_count="single", file_types=[".txt"], elem_classes="upload",
                         label="또는 .txt 파일 업로드 (선택 — 업로드 시 위 대본 대신 사용)")

    with gr.Group(elem_classes="card"):
        with gr.Row():
            filename = gr.Textbox(value="narration", label="파일 이름 (확장자 자동)")
            fmt = gr.Dropdown(FORMAT_LABELS, value="WAV", label="포맷 (WAV = 편집용 / MP3 = 공유)")
        folder = gr.Textbox(value=DEFAULT_OUTPUT, label="저장 폴더",
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

    lang.change(on_lang_change, inputs=lang, outputs=[voice, voice2])
    mix_on.change(lambda on: gr.update(visible=on), inputs=mix_on, outputs=mix_row)
    browse_btn.click(pick_folder, inputs=folder, outputs=folder)
    desktop_btn.click(lambda: str(Path.home() / "Desktop"), outputs=folder)
    downloads_btn.click(lambda: str(Path.home() / "Downloads"), outputs=folder)
    default_btn.click(lambda: DEFAULT_OUTPUT, outputs=folder)
    open_btn.click(open_folder, inputs=folder, outputs=[])
    btn.click(generate,
              inputs=[lang, voice, speed, text, upload, filename, folder,
                      fmt, mix_on, voice2, mix_ratio],
              outputs=[audio_out, status])


if __name__ == "__main__":
    # Gradio 6.0+: theme/css/head 는 launch() 로 전달.
    # allowed_paths: 사용자가 지정한 폴더(보통 홈 디렉터리 하위)의 파일을 브라우저에서 재생/다운로드 허용
    demo.launch(inbrowser=True, allowed_paths=[str(Path.home()), DEFAULT_OUTPUT],
                theme=gr.themes.Base(), css=CSS, head=HEAD)
