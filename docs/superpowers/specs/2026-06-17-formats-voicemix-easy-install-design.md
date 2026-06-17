# 다중 포맷 다운로드 · 목소리 믹스 · 쉬운 설치 설계

- 작성일: 2026-06-17
- 상태: 승인됨 (사용자 승인 후 구현)
- 선행 문서: `2026-06-17-tts-gradio-ui-and-distribution-design.md`
  (해당 문서에서 목소리 섞기·MP3는 YAGNI로 범위 밖이었으나, 이번에 명시적으로 추가 요청됨)

## 목표

1. 생성 음성을 **WAV 외 MP3·FLAC·OGG**로도 저장/다운로드.
2. 프리셋 **목소리 2개를 비율로 섞어**(blend) 새 음색 생성.
3. **git을 전혀 모르는 동업자(윈도우+맥)** 가 압축파일을 받아 **더블클릭 한 번**으로 설치·실행.

웹 UI(`app.py`)와 CLI(`tts.py`) **둘 다**에 1·2 기능을 적용한다.

## 사전 검증 (실측 완료)

| 가정 | 검증 방법 | 결과 |
|------|-----------|------|
| MP3/FLAC/OGG 인코딩이 soundfile만으로 됨 | 0.2초 사인파 write→read 라운드트립 | ✅ 전부 정상 (libsndfile 1.2.2), **ffmpeg 불필요** |
| 목소리 텐서 가중합으로 믹스 가능 | `0.5*af_heart + 0.5*af_bella` 텐서로 합성 | ✅ (510,1,256) 보존, 3.2초 정상 오디오 |
| 새 의존성 필요 없음 | soundfile=인코딩, torch=텐서연산 모두 기설치 | ✅ requirements.txt 변경 0 |

## 결정 사항

| 항목 | 결정 | 이유 |
|------|------|------|
| 포맷 목록 | WAV(기본)·MP3·FLAC·OGG | WAV=편집용 무손실, MP3=공유·미리듣기. soundfile 네이티브. |
| 포맷 기본값 | WAV | 영상 편집기가 무손실을 선호 |
| 믹스 방식 | 같은 언어 내 **2개 + 비율 슬라이더 1개** | 비개발자에게 가장 직관적. N개 가중치는 YAGNI |
| 믹스 언어 제약 | 선택된 언어 내 목소리끼리만 | 언어 파이프라인이 생성마다 고정. 일↔영 혼합 방지 |
| 설치 | OS별 **원클릭 런처 1개**(설치+실행 통합) | "setup 먼저, 그 다음 run" 혼란 제거 |
| Python 버전 | **3.11 고정** | torch 2.5.1+cpu·pyopenjtalk prebuilt가 cp311 기준. 최신 파이썬이면 휠 불일치 |
| 배포 | 깨끗한 ZIP 직접 전달(드라이브/USB) | 동업자 git·GitHub 계정 불필요. `git archive`로 .venv/.git 제외 |
| 새 의존성 | 없음 | 위 검증대로 기존 패키지로 충분 |

## 아키텍처 (기존 공용 코어 유지)

```
kokoro_core.py   # +save_audio(fmt)  +blend_voices(...)  +FORMATS
├── tts.py       # +--format  +--voice2/--mix
└── app.py       # +포맷 드롭다운  +믹스 체크박스/2번째 목소리/비율 슬라이더
```

### kokoro_core.py
- `FORMATS = {"WAV": ".wav", "MP3": ".mp3", "FLAC": ".flac", "OGG": ".ogg"}` (표시명→확장자).
- `save_audio(audio, sr, folder, name, fmt="WAV") -> Path`:
  - `unique_path(folder, sanitize_filename(name), ext=FORMATS[fmt])`로 경로 산출(충돌 시 ` (2)` 증가, 기존 동작 유지).
  - `soundfile.write(path, audio, sr)` (확장자로 포맷 추론). 잘못된 fmt는 `ValueError`.
  - 기존 `save_wav`는 `save_audio(..., "WAV")` 호출하는 얇은 래퍼로 유지(하위호환).
- `blend_voices(lang_code, voice_a, voice_b, ratio) -> torch.FloatTensor`:
  - 같은 언어 파이프라인에서 두 목소리 텐서 로드(`pipe.load_voice`), `ratio*A + (1-ratio)*B` 반환.
  - `ratio`(0~1) = **voice_a 비중**. 1.0=완전 A, 0.0=완전 B, 0.5=균등. 범위 밖이면 `ValueError`.
- `synthesize`는 **변경 없음**: 이미 `voice`를 파이프라인에 그대로 전달하고, 파이프라인은 FloatTensor를 그대로 수용 → 섞은 텐서가 통과.

### app.py (Gradio UI)
- 추가 컨트롤:
  - **포맷** 드롭다운(`list(core.FORMATS)`, 기본 "WAV").
  - **`🎚️ 목소리 섞기`** 체크박스(기본 꺼짐).
  - **목소리 2** 드롭다운 + **비율** 슬라이더(0~1, 기본 0.5, "왼쪽=목소리1 / 오른쪽=목소리2"), 둘 다 체크박스 켜질 때만 `visible`.
- `on_lang_change`: 언어 변경 시 **목소리 1·2 드롭다운 모두** 해당 언어 목록으로 갱신.
- `generate(...)`: 믹스 ON이면 `voice = core.blend_voices(code, v1, v2, 1-ratio_slider)` (슬라이더 오른쪽일수록 voice2↑ 직관 매핑), OFF면 기존 단일 voice. `core.save_audio(..., fmt)`로 저장.
- 출력 오디오 컴포넌트는 저장된 파일 경로를 그대로 재생/다운로드(포맷 그대로).
  - 비고: 브라우저 인라인 재생은 WAV·MP3는 보장, FLAC·OGG는 브라우저마다 다를 수 있음(파일 저장·다운로드는 항상 정상).

### tts.py (CLI)
- `--format {wav,mp3,flac,ogg}` (기본 wav) → 출력 확장자.
- `--voice2 NAME` + `--mix RATIO`(0~1, voice2 비중, 기본 0.5): 지정 시 `core.blend_voices(code, voice, voice2, 1-mix)`로 섞어 합성. 단일 언어(`--lang en|ja`)에서만 허용(이미 `--voice`가 그러함).
- 출력 경로는 기존 고정 경로 `output/<lang>/<stem>.<ext>` 유지(일괄·덮어쓰기 동작 보존).

## 쉬운 설치 (윈도우+맥, ZIP 직접 전달)

### 원클릭 런처 (설치+실행 통합)
- **`시작-윈도우.bat`** (또는 `run-windows.bat`를 스마트화):
  1. `py -3.11` 존재 확인 → 없으면 `winget install -e --id Python.Python.3.11` 시도.
     winget도 없으면 python.org 3.11 다운로드 페이지 안내 후 종료.
  2. `.venv` 없으면 `py -3.11 -m venv .venv` + `pip install -r requirements.txt`.
  3. `app.py` 실행(브라우저 자동 오픈).
- **`시작-맥.command`**:
  1. `python3.11` 존재 확인 → 없으면 설치 안내(python.org 3.11 또는 `brew install python@3.11`) 후 종료(맥은 무인 자동설치 비신뢰 → 안내).
  2. `.venv` 없으면 생성·설치, 있으면 건너뜀.
  3. `app.py` 실행.
  - 첫 줄 실행권한/Gatekeeper 안내는 README에.
- 첫 실행만 느림(설치), 이후 즉시 실행. 기존 `setup-*`는 README에서 "수동 설치(선택)"로 격하하거나 제거.

### 배포용 ZIP 만들기 (개발자용)
- **`make-zip.bat`**(개발자=사용자님 실행): `git archive --format=zip -o dist/foreign-video-tts.zip HEAD`.
  - 추적 파일만 포함 → `.venv/.git/__pycache__/output 오디오` 자동 제외(.gitignore 반영).
  - 산출된 `dist/foreign-video-tts.zip`을 동업자에게 전달.

### README
- "MP3는 ffmpeg로" 줄 **삭제**(앱 내 지원으로 대체).
- 포맷 선택·목소리 믹스 사용법, CLI 새 옵션 추가.
- 동업자용 절차: ZIP 풀기 → 윈도우는 `시작-윈도우.bat` / 맥은 `시작-맥.command` 더블클릭(첫 실행 시 자동 설치) → 끝. Python 미설치 시 동작·맥 우클릭→열기 안내.

## 구현 순서
1. 설계 문서 작성·커밋(본 문서).
2. `kokoro_core.py`: `save_audio`/`blend_voices`/`FORMATS` 추가 → 순수함수 단위테스트(포맷 매핑·블렌드 shape/math·파일명).
3. `tts.py`: 옵션 추가 → 샘플 1건 `--format mp3`, `--voice2 ... --mix` 실행 회귀.
4. `app.py`: 컨트롤 추가 → 헤드리스 서버 기동으로 import/배선 오류 없음 확인.
5. 설치 스크립트(win/mac) + `make-zip.bat`.
6. `README.md` 갱신.
7. 전체 커밋. (브라우저 실제 클릭·맥 실행은 사용자/동업자 확인 — 정직한 범위.)

## 검증 계획
- 순수함수: pytest/스크립트로 `save_audio`(각 포맷 실제 파일 생성·재읽기), `blend_voices`(shape 보존·가중치 경계), `sanitize_filename`/`unique_path`(충돌 증가).
- CLI: `tts.py --lang en --format mp3`, `--voice2 af_bella --mix 0.3` 1건씩 생성 확인.
- 웹: `app.py`를 짧게 기동→정상 로드 로그 확인 후 종료(실클릭은 사용자 확인).
- 설치 스크립트: 로직(존재검사 분기) 리뷰 + 윈도우에서 기존 `.venv` 재사용 경로 동작 확인. winget 신규설치·맥 경로는 동업자 환경 첫 실행에서 확인.

## 범위 밖 (YAGNI)
- 자막(.srt), 번역, 음성 복제, 3개 이상 목소리 가중치, 클라우드 호스팅, .exe/.app 단일 실행파일 패키징, winget 외 패키지 매니저 자동설치.
