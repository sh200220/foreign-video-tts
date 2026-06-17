"""
Kokoro TTS 일괄 생성기 (CLI)
============================
scripts/en, scripts/ja 폴더의 .txt 대본을 읽어 output/en, output/ja 에 .wav 로 저장.
음성 생성 로직은 kokoro_core 모듈을 공유한다 (웹 UI app.py 와 동일 코어).

사용 예:
    python tts.py                      # en, ja 전부
    python tts.py --lang ja            # 일본어만
    python tts.py --lang en --voice am_michael --speed 1.1
"""

import argparse
import sys
from pathlib import Path

import soundfile as sf

import kokoro_core as core

# 폴더명 -> (Kokoro lang_code, 기본 목소리)
FOLDER_LANG = {
    "en": ("a", "af_heart"),   # 영어(미국)
    "ja": ("j", "jf_alpha"),   # 일본어
}

ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT / "scripts"
OUTPUT_DIR = ROOT / "output"


def find_text_files(folder_name):
    folder = SCRIPTS_DIR / folder_name
    if not folder.is_dir():
        return []
    return sorted(folder.glob("*.txt"))


def main():
    parser = argparse.ArgumentParser(description="Kokoro TTS 일괄 생성기")
    parser.add_argument("--lang", choices=["en", "ja", "all"], default="all",
                        help="처리할 언어 (기본: all)")
    parser.add_argument("--voice", default=None,
                        help="목소리 강제 지정 (단일 언어일 때만). --lang all 과 함께 쓸 수 없음")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="말하기 속도 배율 (기본 1.0)")
    args = parser.parse_args()

    if args.voice and args.lang == "all":
        print("[오류] --voice 는 언어별로 목소리가 달라 --lang en 또는 --lang ja 와 함께 쓰세요.")
        sys.exit(2)

    folders = ["en", "ja"] if args.lang == "all" else [args.lang]

    total = 0
    for folder_name in folders:
        code, default_voice = FOLDER_LANG[folder_name]
        files = find_text_files(folder_name)
        if not files:
            print(f"[{folder_name}] scripts/{folder_name}/ 에 .txt 파일이 없습니다. 건너뜁니다.")
            continue
        voice = args.voice or default_voice
        print(f"[{folder_name}] {len(files)}개 파일 처리 중 (목소리={voice}) ...")
        for txt in files:
            out = OUTPUT_DIR / folder_name / (txt.stem + ".wav")
            try:
                audio, sr = core.synthesize(txt.read_text(encoding="utf-8"), code, voice, args.speed)
                out.parent.mkdir(parents=True, exist_ok=True)
                sf.write(str(out), audio, sr)
                print(f"  [완료] {out.relative_to(ROOT)}  ({len(audio) / sr:.1f}초)")
                total += 1
            except ValueError as e:
                print(f"  [건너뜀] {txt.name}: {e}")
            except Exception as e:
                print(f"  [오류] {txt.name}: {e}")

    print(f"\n총 {total}개 음성 파일 생성 완료. output/ 폴더를 확인하세요.")


if __name__ == "__main__":
    main()
