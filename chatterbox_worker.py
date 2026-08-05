"""
Chatterbox 고품질 TTS 워커 (별도 가상환경 .venv-chatterbox 에서 실행)
=====================================================================
chatterbox_engine.py 가 서브프로세스로 띄우는 상주 워커.
표준입력 한 줄 = 요청 JSON, 표준출력 한 줄 = 응답 JSON. (UTF-8)

  요청:  {"text": str, "lang": "en|ja|ko", "exaggeration": float, "cfg": float, "out": "저장할.wav"}
  응답:  {"ok": true, "path": str, "dur": float} 또는 {"ok": false, "error": str}

시작하면 모델을 1회 로드(CUDA 가능하면 GPU, 아니면 CPU)하고
{"ready": true, "device": ..., "sr": ...} 를 먼저 출력한다.
stdin 이 닫히면(부모 앱 종료) 함께 종료된다.

라이선스: Chatterbox(MIT, 상업 사용 가능). 모든 출력에 비가청 워터마크(Perth)가 들어간다.
"""

import json
import sys

sys.stdin.reconfigure(encoding="utf-8", errors="replace")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def say(obj):
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def main():
    try:
        import torch
        import torchaudio
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    except Exception as e:
        say({"ready": False, "error": f"{type(e).__name__}: {e}"})
        return 1
    say({"ready": True, "device": device, "sr": int(model.sr)})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            wav = model.generate(
                req["text"],
                language_id=req["lang"],
                exaggeration=float(req.get("exaggeration", 0.5)),
                cfg_weight=float(req.get("cfg", 0.5)),
            )
            torchaudio.save(req["out"], wav, model.sr)
            say({"ok": True, "path": req["out"], "dur": wav.shape[-1] / model.sr})
        except Exception as e:
            say({"ok": False, "error": f"{type(e).__name__}: {e}"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
