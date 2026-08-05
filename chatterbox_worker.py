"""
Chatterbox 고품질 TTS 워커 (별도 가상환경 .venv-chatterbox 에서 실행)
=====================================================================
chatterbox_engine.py 가 서브프로세스로 띄우는 상주 워커.
표준입력 한 줄 = 요청 JSON, 표준출력 한 줄 = 응답 JSON. (UTF-8)

  요청:  {"text": str, "lang": "en|ja|ko", "exaggeration": float, "cfg": float,
          "out": "저장할.wav", "prompt": "참고목소리.wav(선택; 없으면 내장 목소리)"}
  응답:  {"ok": true, "path": str, "dur": float} 또는 {"ok": false, "error": str}

같은 prompt 가 연속되면 목소리 조건(conditionals)을 캐시해 줄마다 재계산하지 않는다.

시작하면 모델을 1회 로드(CUDA 가능하면 GPU, 아니면 CPU)하고
{"ready": true, "device": ..., "sr": ...} 를 먼저 출력한다.
stdin 이 닫히면(부모 앱 종료) 함께 종료된다.

라이선스: Chatterbox(MIT, 상업 사용 가능). 모든 출력에 비가청 워터마크(Perth)가 들어간다.
"""

import json
import os
import sys

sys.stdin.reconfigure(encoding="utf-8", errors="replace")

# 프로토콜 전용 스트림: 진짜 stdout(fd 1)을 복제해 확보하고,
# 이후 라이브러리들의 print(예: PerthNet 로드 메시지)는 전부 stderr 로 보낸다.
# -> 부모(chatterbox_engine)는 fd 1 에서 순수 JSON 라인만 받는다.
_PROTO = os.fdopen(os.dup(1), "w", encoding="utf-8", errors="replace")
sys.stdout = sys.stderr


def say(obj):
    _PROTO.write(json.dumps(obj, ensure_ascii=False) + "\n")
    _PROTO.flush()


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

    default_conds = model.conds     # 내장 기본 목소리 조건
    cur_prompt = None               # 마지막으로 준비한 참고 목소리 경로 (캐시 키)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            ex = float(req.get("exaggeration", 0.5))
            prompt = req.get("prompt") or None
            if prompt != cur_prompt:            # 목소리가 바뀔 때만 조건 재계산
                if prompt:
                    model.prepare_conditionals(prompt, exaggeration=ex)
                else:
                    model.conds = default_conds
                cur_prompt = prompt
            wav = model.generate(               # prompt 없이 호출 -> 캐시된 조건 재사용
                req["text"],
                language_id=req["lang"],
                exaggeration=ex,
                cfg_weight=float(req.get("cfg", 0.5)),
            )
            torchaudio.save(req["out"], wav, model.sr)
            say({"ok": True, "path": req["out"], "dur": wav.shape[-1] / model.sr})
        except Exception as e:
            say({"ok": False, "error": f"{type(e).__name__}: {e}"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
