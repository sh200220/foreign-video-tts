"""
Kokoro TTS 일괄 생성기
=======================
scripts/en, scripts/ja 폴더 안의 .txt 대본을 읽어
output/en, output/ja 폴더에 같은 이름의 .wav 음성으로 저장합니다.

사용 예:
    python tts.py                      # en, ja 전부 처리
    python tts.py --lang ja            # 일본어만
    python tts.py --lang en --voice am_michael --speed 1.1

라이선스: Kokoro(Apache 2.0) — 상업적 사용 가능. 자세한 내용은 README.md 참고.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

# 폴더명 -> (Kokoro lang_code, 기본 목소리)
#   lang_code: 'a' = American English, 'b' = British English, 'j' = Japanese
LANG_CONFIG = {
    "en": {"lang_code": "a", "voice": "af_heart"},
    "ja": {"lang_code": "j", "voice": "jf_alpha"},
}

SAMPLE_RATE = 24000  # Kokoro 출력 샘플레이트(Hz)

ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT / "scripts"
OUTPUT_DIR = ROOT / "output"


def to_numpy(audio):
    """Kokoro가 돌려주는 오디오(torch 텐서 또는 배열)를 numpy float 배열로 변환."""
    if hasattr(audio, "detach"):
        return audio.detach().cpu().numpy()
    return np.asarray(audio)


def find_text_files(lang):
    folder = SCRIPTS_DIR / lang
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.txt"))


def synthesize_file(pipeline, txt_path, out_path, voice, speed):
    text = txt_path.read_text(encoding="utf-8").strip()
    if not text:
        print(f"  [건너뜀] 내용이 비어 있음: {txt_path.name}")
        return False

    chunks = []
    # 긴 대본은 줄바꿈 기준으로 자동 분할되어 여러 조각으로 생성됨 → 이어붙임
    for _, _, audio in pipeline(text, voice=voice, speed=speed, split_pattern=r"\n+"):
        chunks.append(to_numpy(audio))

    if not chunks:
        print(f"  [실패] 오디오가 생성되지 않음: {txt_path.name}")
        return False

    full = np.concatenate(chunks)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), full, SAMPLE_RATE)
    dur = len(full) / SAMPLE_RATE
    print(f"  [완료] {out_path.relative_to(ROOT)}  ({dur:.1f}초)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Kokoro TTS 일괄 생성기")
    parser.add_argument("--lang", choices=["en", "ja", "all"], default="all",
                        help="처리할 언어 (기본: all)")
    parser.add_argument("--voice", default=None,
                        help="목소리 강제 지정 (예: am_michael, jf_alpha). "
                             "미지정 시 언어별 기본값 사용. --lang all 과 함께 쓸 수 없음")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="말하기 속도 배율 (기본 1.0, 예: 0.9는 느리게 1.2는 빠르게)")
    args = parser.parse_args()

    if args.voice and args.lang == "all":
        print("[오류] --voice 는 언어별로 목소리가 다르므로 --lang en 또는 --lang ja 와 함께 쓰세요.")
        print("       (전체 처리 시 목소리는 tts.py 상단 LANG_CONFIG 에서 기본값을 바꾸면 됩니다.)")
        sys.exit(2)

    try:
        from kokoro import KPipeline
    except ImportError:
        print("[오류] kokoro 가 설치되어 있지 않습니다. 아래로 설치하세요:")
        print("       pip install -r requirements.txt")
        sys.exit(1)

    langs = ["en", "ja"] if args.lang == "all" else [args.lang]

    total_done = 0
    for lang in langs:
        cfg = LANG_CONFIG[lang]
        files = find_text_files(lang)
        if not files:
            print(f"[{lang}] scripts/{lang}/ 에 .txt 파일이 없습니다. 건너뜁니다.")
            continue

        print(f"[{lang}] {len(files)}개 파일 처리 중 (lang_code={cfg['lang_code']}) ...")
        pipeline = KPipeline(lang_code=cfg["lang_code"])  # 언어별로 한 번만 로드
        voice = args.voice or cfg["voice"]

        for txt in files:
            out = OUTPUT_DIR / lang / (txt.stem + ".wav")
            try:
                if synthesize_file(pipeline, txt, out, voice, args.speed):
                    total_done += 1
            except Exception as e:
                print(f"  [오류] {txt.name} 처리 실패: {e}")

    print(f"\n총 {total_done}개 음성 파일 생성 완료. output/ 폴더를 확인하세요.")


if __name__ == "__main__":
    main()
