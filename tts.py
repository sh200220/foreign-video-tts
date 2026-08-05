"""
TTS 일괄 생성기 (CLI)
=====================
scripts/en, scripts/ja, scripts/ko 폴더의 .txt 대본을 읽어 output/<언어> 에 저장.
음성 생성 로직은 kokoro_core 모듈을 공유한다 (웹 UI app.py 와 동일 코어).

사용 예:
    python tts.py                      # en, ja, ko 전부
    python tts.py --lang ja            # 일본어만
    python tts.py --lang ko --voice M2 # 한국어, 남성 목소리
    python tts.py --lang en --voice am_michael --speed 1.1
"""

import argparse
import sys
from pathlib import Path

import soundfile as sf

import kokoro_core as core

# 콘솔이 cp949(한국 윈도우)여도 한국어 출력이 깨지지 않도록 UTF-8 로 고정
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 폴더명 -> (lang_code, 기본 목소리)
FOLDER_LANG = {
    "en": ("a", "af_heart"),   # 영어(미국, Kokoro)
    "ja": ("j", "jf_alpha"),   # 일본어(Kokoro)
    "ko": ("k", "F1"),         # 한국어(Supertonic)
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
    parser = argparse.ArgumentParser(description="TTS 일괄 생성기 (Kokoro + Supertonic)")
    parser.add_argument("--lang", choices=["en", "ja", "ko", "all"], default="all",
                        help="처리할 언어 (기본: all)")
    parser.add_argument("--voice", default=None,
                        help="목소리 강제 지정 (단일 언어일 때만). --lang all 과 함께 쓸 수 없음")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="말하기 속도 배율 (기본 1.0)")
    parser.add_argument("--format", choices=["wav", "mp3", "flac", "ogg"], default="wav",
                        help="출력 포맷 (기본: wav)")
    parser.add_argument("--voice2", default=None,
                        help="두 번째 목소리(믹스용, 단일 언어일 때만). 지정하면 --voice 와 섞음")
    parser.add_argument("--mix", type=float, default=0.5,
                        help="믹스 비율 = voice2 비중 0~1 (기본 0.5=균등). --voice2 와 함께 사용")
    args = parser.parse_args()

    if (args.voice or args.voice2) and args.lang == "all":
        print("[오류] --voice/--voice2 는 언어별로 달라 --lang en/ja/ko 와 함께 쓰세요.")
        sys.exit(2)
    if args.voice2 and not 0.0 <= args.mix <= 1.0:
        print(f"[오류] --mix 는 0~1 사이여야 합니다: {args.mix}")
        sys.exit(2)

    ext = core.FORMATS[args.format.upper()]
    folders = ["en", "ja", "ko"] if args.lang == "all" else [args.lang]

    total = 0
    for folder_name in folders:
        code, default_voice = FOLDER_LANG[folder_name]
        files = find_text_files(folder_name)
        if not files:
            print(f"[{folder_name}] scripts/{folder_name}/ 에 .txt 파일이 없습니다. 건너뜁니다.")
            continue
        base_voice = args.voice or default_voice
        if args.voice2:
            # ratio = 목소리 A(base) 비중 = 1 - (voice2 비중)
            voice = core.blend_voices(code, base_voice, args.voice2, 1.0 - args.mix)
            voice_label = f"{base_voice}+{args.voice2} (voice2 {int(args.mix * 100)}%)"
        else:
            voice = base_voice
            voice_label = base_voice
        print(f"[{folder_name}] {len(files)}개 파일 처리 중 (목소리={voice_label}, 포맷={args.format}) ...")
        for txt in files:
            out = OUTPUT_DIR / folder_name / (txt.stem + ext)
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
