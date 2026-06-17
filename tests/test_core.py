"""
kokoro_core 순수 함수 테스트 (프레임워크 불필요)
================================================
실행:  .\.venv\Scripts\python.exe tests\test_core.py   (윈도우)
       ./.venv/bin/python tests/test_core.py            (맥)

모델/네트워크를 쓰지 않는 순수 로직만 검증한다:
  - blend_style  : 목소리 텐서 가중합(믹싱) 수학
  - save_audio   : 포맷->확장자 매핑·파일 저장·충돌 증가
  - FORMATS      : 지원 포맷 표
실제 음성 합성·블렌드 end-to-end 는 별도(수동) 확인 대상.
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

# 콘솔이 cp949(한국 윈도우)여도 출력이 깨지지 않도록 UTF-8 로 고정
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 프로젝트 루트를 import 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kokoro_core as core

_failures = []


def check(name, fn):
    try:
        fn()
        print(f"  [PASS] {name}")
    except AssertionError as e:
        print(f"  [FAIL] {name}: {e}")
        _failures.append(name)
    except Exception as e:
        print(f"  [ERROR] {name}: {type(e).__name__}: {e}")
        _failures.append(name)


# ---------------- blend_style (믹싱 수학) ----------------

def test_blend_ratio_1_returns_a():
    a = torch.ones(4, 1, 3)
    b = torch.zeros(4, 1, 3)
    out = core.blend_style(a, b, 1.0)
    assert torch.allclose(out, a), "ratio=1.0 이면 목소리 A 그대로여야 함"


def test_blend_ratio_0_returns_b():
    a = torch.ones(4, 1, 3)
    b = torch.zeros(4, 1, 3)
    out = core.blend_style(a, b, 0.0)
    assert torch.allclose(out, b), "ratio=0.0 이면 목소리 B 그대로여야 함"


def test_blend_half_is_mean():
    a = torch.full((4, 1, 3), 2.0)
    b = torch.full((4, 1, 3), 4.0)
    out = core.blend_style(a, b, 0.5)
    assert torch.allclose(out, torch.full((4, 1, 3), 3.0)), "0.5 면 평균(3.0)이어야 함"


def test_blend_preserves_shape():
    a = torch.rand(510, 1, 256)
    b = torch.rand(510, 1, 256)
    out = core.blend_style(a, b, 0.3)
    assert tuple(out.shape) == (510, 1, 256), f"shape 보존 실패: {tuple(out.shape)}"


def test_blend_ratio_out_of_range_raises():
    a = torch.ones(2, 1, 3); b = torch.zeros(2, 1, 3)
    for bad in (-0.1, 1.5):
        try:
            core.blend_style(a, b, bad)
            assert False, f"ratio={bad} 는 ValueError 여야 함"
        except ValueError:
            pass


def test_blend_shape_mismatch_raises():
    a = torch.ones(4, 1, 3); b = torch.ones(5, 1, 3)
    try:
        core.blend_style(a, b, 0.5)
        assert False, "shape 불일치는 ValueError 여야 함"
    except ValueError:
        pass


# ---------------- FORMATS / save_audio ----------------

def test_formats_table():
    assert core.FORMATS["WAV"] == ".wav"
    assert core.FORMATS["MP3"] == ".mp3"
    assert core.FORMATS["FLAC"] == ".flac"
    assert core.FORMATS["OGG"] == ".ogg"


def _sine(sr=24000, sec=0.1):
    t = np.linspace(0, sec, int(sr * sec), endpoint=False)
    return (0.3 * np.sin(2 * np.pi * 440 * t)).astype("float32"), sr


def test_save_audio_each_format_roundtrip():
    import soundfile as sf
    audio, sr = _sine()
    with tempfile.TemporaryDirectory() as d:
        for fmt, ext in core.FORMATS.items():
            p = core.save_audio(audio, sr, d, "clip", fmt)
            assert p.suffix == ext, f"{fmt}: 확장자 {p.suffix} != {ext}"
            assert p.exists(), f"{fmt}: 파일이 없음"
            back, _ = sf.read(str(p))
            assert len(back) > 0, f"{fmt}: 다시 읽은 오디오가 비어 있음"


def test_save_audio_fmt_case_insensitive():
    audio, sr = _sine()
    with tempfile.TemporaryDirectory() as d:
        p = core.save_audio(audio, sr, d, "clip", "mp3")  # 소문자도 허용
        assert p.suffix == ".mp3", f"소문자 fmt 처리 실패: {p.suffix}"


def test_save_audio_invalid_format_raises():
    audio, sr = _sine()
    with tempfile.TemporaryDirectory() as d:
        try:
            core.save_audio(audio, sr, d, "clip", "XYZ")
            assert False, "지원하지 않는 포맷은 ValueError 여야 함"
        except ValueError:
            pass


def test_save_audio_collision_increments():
    audio, sr = _sine()
    with tempfile.TemporaryDirectory() as d:
        p1 = core.save_audio(audio, sr, d, "clip", "WAV")
        p2 = core.save_audio(audio, sr, d, "clip", "WAV")
        assert p1.name == "clip.wav", f"첫 저장 이름: {p1.name}"
        assert p2.name == "clip (2).wav", f"충돌 시 증가 실패: {p2.name}"


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    print(f"kokoro_core 순수 함수 테스트 - {len(tests)}개\n")
    for fn in tests:
        check(fn.__name__, fn)
    print()
    if _failures:
        print(f"실패 {len(_failures)}개: {', '.join(_failures)}")
        sys.exit(1)
    print(f"전부 통과 ({len(tests)}개).")


if __name__ == "__main__":
    main()
