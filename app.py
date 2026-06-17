"""
외국어 영상 TTS — 웹 UI (Gradio)
=================================
브라우저에서 언어·목소리·속도를 고르고 대본을 넣으면 음성(.wav)을 만들어
원하는 폴더에 원하는 이름으로 저장한다. (음성 생성은 kokoro_core 공유)

실행:  python app.py   (브라우저가 자동으로 열립니다)
"""

from pathlib import Path

import gradio as gr

import kokoro_core as core

DEFAULT_OUTPUT = str((Path(__file__).resolve().parent / "output").resolve())
LANG_LABELS = list(core.LANGS.keys())
FIRST_LANG = LANG_LABELS[0]
FIRST_CODE = core.LANGS[FIRST_LANG]["code"]


def on_lang_change(lang_label):
    """언어 바뀌면 목소리 드롭다운을 해당 언어 목록으로 갱신."""
    info = core.LANGS[lang_label]
    return gr.update(choices=core.voices_for(info["code"]), value=info["default_voice"])


def generate(lang_label, voice, speed, text, uploaded_file, filename, folder):
    # 업로드한 .txt가 있으면 그것을, 없으면 텍스트박스 내용을 사용
    content = text
    if uploaded_file:
        content = Path(uploaded_file).read_text(encoding="utf-8")

    code = core.LANGS[lang_label]["code"]
    try:
        audio, sr = core.synthesize(content, code, voice, speed)
    except ValueError as e:
        raise gr.Error(str(e))

    path = core.save_wav(audio, sr, folder or DEFAULT_OUTPUT, filename)
    dur = len(audio) / sr
    return str(path), f"✅ 저장됨: `{path}`  ({dur:.1f}초)"


with gr.Blocks(title="외국어 영상 TTS") as demo:
    gr.Markdown(
        "# 🎬 외국어 영상 TTS\n"
        "Kokoro 기반 · 일본어/영어 내레이션 음성 생성. 무료·로컬 동작."
    )
    with gr.Row():
        lang = gr.Dropdown(LANG_LABELS, value=FIRST_LANG, label="언어")
        voice = gr.Dropdown(core.voices_for(FIRST_CODE),
                            value=core.LANGS[FIRST_LANG]["default_voice"], label="목소리")
        speed = gr.Slider(0.5, 2.0, value=1.0, step=0.05, label="속도 (1.0 = 보통)")

    text = gr.Textbox(lines=6, label="대본",
                      placeholder="여기에 대본을 붙여넣으세요. 문장/문단마다 줄바꿈하면 더 자연스럽습니다.")
    upload = gr.File(file_count="single", file_types=[".txt"],
                     label="또는 .txt 파일 업로드 (선택 — 업로드 시 위 대본 대신 사용)")

    with gr.Row():
        filename = gr.Textbox(value="narration", label="파일 이름 (.wav 자동)")
        folder = gr.Textbox(value=DEFAULT_OUTPUT, label="저장 폴더")

    btn = gr.Button("🔊 생성하기", variant="primary")
    audio_out = gr.Audio(label="결과 (재생 / 다운로드)", type="filepath")
    status = gr.Markdown()

    lang.change(on_lang_change, inputs=lang, outputs=voice)
    btn.click(generate,
              inputs=[lang, voice, speed, text, upload, filename, folder],
              outputs=[audio_out, status])


if __name__ == "__main__":
    # allowed_paths: 사용자가 지정한 폴더(보통 홈 디렉터리 하위)의 파일을 브라우저에서 재생/다운로드 허용
    demo.launch(inbrowser=True, allowed_paths=[str(Path.home()), DEFAULT_OUTPUT])
