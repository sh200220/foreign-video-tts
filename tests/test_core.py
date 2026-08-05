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


# ---------------- 한국어 엔진 등록 / 속도 클램프 ----------------

def test_korean_lang_registered():
    assert "한국어" in core.LANGS, "LANGS 에 한국어가 있어야 함"
    assert core.LANGS["한국어"]["code"] == "k"
    assert core.LANGS["한국어"]["default_voice"] == "F1"
    assert core.voices_for("k") == ["F1", "F2", "F3", "F4", "F5",
                                    "M1", "M2", "M3", "M4", "M5"]


def test_sample_rate_per_engine():
    assert core.sample_rate_for("a") == 24000
    assert core.sample_rate_for("j") == 24000
    assert core.sample_rate_for("k") == 44100


def test_clamp_speed():
    assert core.clamp_speed("k", 0.5) == 0.7, "한국어는 0.7 미만 클램프"
    assert core.clamp_speed("k", 2.5) == 2.0
    assert core.clamp_speed("k", 1.0) == 1.0
    assert core.clamp_speed("a", 0.5) == 0.5, "Kokoro 는 그대로"


def test_blend_korean_raises():
    try:
        core.blend_voices("k", "F1", "F2", 0.5)
        assert False, "한국어 blend 는 ValueError 여야 함"
    except ValueError:
        pass


# ---------------- 인라인 쉼 태그 ----------------

def test_pause_tags_midline():
    parts = core.split_pause_tags("안녕하세요 [쉼:1.5] 반갑습니다")
    assert parts == [("text", "안녕하세요"), ("pause", 1.5), ("text", "반갑습니다")], parts


def test_pause_tags_fullwidth_and_clamp():
    parts = core.split_pause_tags("[쉼：99]")
    assert parts == [("pause", 10.0)], f"전각 콜론 + 10초 클램프 실패: {parts}"


def test_pause_tags_invalid_kept_as_text():
    parts = core.split_pause_tags("[쉼:abc] 본문")
    assert parts == [("text", "[쉼:abc] 본문")], parts


def test_pause_tags_none():
    assert core.split_pause_tags("그냥 문장") == [("text", "그냥 문장")]


def test_pause_tags_empty_line():
    assert core.split_pause_tags("   ") == []


def test_strip_pause_tags_for_caption():
    assert core.strip_pause_tags("앞 [쉼:2] 뒤") == "앞 뒤"


# ---------------- 대화 모드 (화자 매핑) ----------------

def test_parse_voice_map():
    m = core.parse_voice_map("A=af_heart\n B = am_michael \n\n")
    assert m == {"A": "af_heart", "B": "am_michael"}, m


def test_parse_voice_map_empty():
    assert core.parse_voice_map("") == {}
    assert core.parse_voice_map(None) == {}


def test_parse_voice_map_bad_line_raises():
    try:
        core.parse_voice_map("A-af_heart")
        assert False, "= 없는 줄은 ValueError 여야 함"
    except ValueError:
        pass


def test_match_speaker():
    vm = {"A": "af_heart", "나레이터": "am_adam"}
    assert core.match_speaker("A: 안녕", vm) == ("af_heart", "안녕")
    assert core.match_speaker("나레이터： 시작합니다", vm) == ("am_adam", "시작합니다")
    assert core.match_speaker("A : 공백 허용", vm) == ("af_heart", "공백 허용")
    assert core.match_speaker("참고: 이 줄은 그대로", vm) == (None, "참고: 이 줄은 그대로")
    assert core.match_speaker("콜론 없는 줄", vm) == (None, "콜론 없는 줄")


# ---------------- 고품질(Chatterbox) 모드 ----------------

def test_chatterbox_langs_registered():
    for label, code, base in [("영어 (고품질·감정)", "ce", "en"),
                              ("일본어 (고품질·감정)", "cj", "ja"),
                              ("한국어 (고품질·감정)", "ck", "ko")]:
        assert label in core.LANGS, f"LANGS 에 {label} 이 있어야 함"
        assert core.LANGS[label]["code"] == code
        assert core.CHATTERBOX_CODES[code] == base
        voices = core.voices_for(code)      # 참고목소리 폴더 내용에 따라 늘어날 수 있음
        assert voices[0] == "기본 목소리", voices


def test_chatterbox_reference_voices():
    import chatterbox_engine as cb
    with tempfile.TemporaryDirectory() as d:
        assert cb.list_voices(d) == ["기본 목소리"], "빈 폴더면 기본 목소리만"
        (Path(d) / "사장님.wav").write_bytes(b"RIFF")
        (Path(d) / "동업자.mp3").write_bytes(b"ID3")
        (Path(d) / "메모.txt").write_bytes(b"x")         # 오디오 아님 -> 제외
        assert cb.list_voices(d) == ["기본 목소리", "동업자", "사장님"]
        assert cb._voice_path("기본 목소리", d) is None
        assert cb._voice_path("사장님", d).name == "사장님.wav"
        try:
            cb._voice_path("없는이름", d)
            assert False, "없는 목소리는 RuntimeError 여야 함"
        except RuntimeError as e:
            assert "새로고침" in str(e)


def test_supports_mix():
    for code in ("a", "b", "j"):
        assert core.supports_mix(code), f"{code} 는 목소리 섞기 지원"
    for code in ("k", "ce", "cj", "ck"):
        assert not core.supports_mix(code), f"{code} 는 목소리 섞기 미지원"


def test_chatterbox_sample_rate_and_speed():
    assert core.sample_rate_for("ce") == 24000
    assert core.clamp_speed("ce", 1.7) == 1.0, "고품질 모드는 속도 미지원 -> 1.0 고정"


def test_blend_chatterbox_raises():
    try:
        core.blend_voices("cj", "기본 목소리", "기본 목소리", 0.5)
        assert False, "고품질 모드 blend 는 ValueError 여야 함"
    except ValueError:
        pass


def test_chatterbox_control_ranges():
    import chatterbox_engine as cb
    assert cb.EMOTION_MIN <= cb.DEFAULT_EMOTION <= cb.EMOTION_MAX
    assert cb.PACE_MIN <= cb.DEFAULT_PACE <= cb.PACE_MAX
    assert (cb.DEFAULT_EMOTION, cb.DEFAULT_PACE) == (0.5, 0.5), "기본값은 모델 권장 0.5/0.5"


# ---------------- 쉼 인접 가장자리 트림 ----------------

def test_trim_edge_sides():
    sr = 1000
    silence = np.zeros(500, dtype="float32")
    tone = np.full(300, 0.5, dtype="float32")
    audio = np.concatenate([silence, tone, silence])   # 500 + 300 + 500
    assert len(core._trim_edge(audio, sr, lead=True)) == 800, "앞무음만 제거"
    assert len(core._trim_edge(audio, sr, trail=True)) == 800, "뒤무음만 제거"
    assert len(core._trim_edge(audio, sr, lead=True, trail=True)) == 300, "양쪽 제거"
    assert len(core._trim_edge(audio, sr)) == 1300, "옵션 없으면 그대로"
    assert len(core._trim_edge(silence, sr, lead=True)) == 0, "전부 무음이면 빈 배열"


# ---------------- 자막 줄 규격화 ----------------

def test_srt_split_disabled():
    segs = [("아주 긴 자막 텍스트", 0.0, 5.0)]
    assert core.split_segments_for_srt(segs, 0) == segs
    assert core.split_segments_for_srt(segs, None) == segs


def test_srt_split_space_boundary_and_timing():
    segs = [("hello world again", 0.0, 3.0)]
    out = core.split_segments_for_srt(segs, 11)
    assert [t for t, _, _ in out] == ["hello world", "again"], out
    assert out[0][1] == 0.0 and abs(out[-1][2] - 3.0) < 1e-6
    assert abs(out[0][2] - out[1][1]) < 1e-6, "조각들이 이어져야 함"
    d0 = out[0][2] - out[0][1]
    d1 = out[1][2] - out[1][1]
    assert d0 > d1, "긴 조각이 더 긴 시간을 가져야 함"


def test_srt_split_punct_boundary_cjk():
    segs = [("こんにちは。ようこそ、皆さん", 0.0, 4.0)]
    out = core.split_segments_for_srt(segs, 8)
    assert out[0][0] == "こんにちは。", f"문장부호 뒤 분할 실패: {out[0][0]}"


def test_srt_split_forced():
    segs = [("가나다라마바사아자차", 0.0, 2.0)]
    out = core.split_segments_for_srt(segs, 4)
    assert [t for t, _, _ in out] == ["가나다라", "마바사아", "자차"], out


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
