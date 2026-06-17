# TTS Gradio UI + 크로스플랫폼 배포 설계

- 작성일: 2026-06-17
- 상태: 승인됨 (사용자 승인 후 구현)
- 선행 문서: `2026-06-17-kokoro-tts-video-workflow-design.md` (기본 Kokoro 워크플로우)

## 목표

비개발자 동업자(맥·윈도우 보유)가 **브라우저에서 클릭·드롭다운으로** 일본어·영어 음성을 만들 수 있게 한다.
기존 폴더 일괄 처리 CLI(`tts.py`)는 유지하고, 같은 코어를 쓰는 **Gradio 웹 UI**를 추가한다.
**비공개 GitHub 저장소**로 배포한다.

## 결정 사항

| 항목 | 결정 | 이유 |
|------|------|------|
| 인터페이스 | Gradio 웹 UI(브라우저) | 동업자가 비개발 → 드롭다운/슬라이더가 가장 친절, 크로스플랫폼, 무료 |
| 노출 옵션 | 언어 / 목소리 / 속도 / 텍스트·파일 입력 / 파일이름·저장폴더 | Kokoro가 실제 조절 가능한 범위(음색·감정 조절은 없음) |
| 목소리 섞기·MP3 | 범위 밖(추후 추가 가능) | YAGNI |
| 기존 CLI | 유지 | 사용자님 일괄 처리 워크플로우 보존 |
| 배포 | 비공개 GitHub 저장소(`gh`로 생성·push) | 상업용 → private. 동업자 초대로 다운로드·업데이트 용이 |

## 아키텍처

음성 생성 로직을 공용 코어로 분리하여 CLI와 UI가 공유(중복 제거).

```
kokoro_core.py   # synthesize(text, lang, voice, speed) -> numpy audio; 목소리 목록 제공
├── tts.py       # 기존 폴더 일괄 처리 CLI (코어 사용하도록 리팩터)
└── app.py       # Gradio 웹 UI (코어 사용)
```

### kokoro_core.py (공용)
- `LANGS`: {en-US:('a',...), en-UK:('b',...), ja:('j',...)} 및 언어별 목소리 목록.
- `list_voices(lang)`: 해당 언어 프리셋 목록 반환(UI 드롭다운용).
- `synthesize(text, lang, voice, speed) -> (audio_np, sample_rate)`: 파이프라인 로드(언어별 캐시)·분할·concat.
- 파이프라인 인스턴스를 언어별로 캐싱(반복 호출 시 재로딩 방지).

### app.py (Gradio UI)
- 컨트롤: 언어 드롭다운 → 변경 시 목소리 드롭다운 갱신, 속도 슬라이더(0.5~2.0, 기본 1.0),
  대본 텍스트박스 + `.txt` 업로드, **파일 이름** 입력, **저장 폴더** 입력, [생성] 버튼.
- 출력: 오디오 플레이어(재생/다운로드) + "저장됨: <경로>" 상태 메시지.
- 한국어 라벨. `demo.launch(inbrowser=True)`로 브라우저 자동 오픈.

### 파일 이름·저장 위치 동작
- 파일 이름: 금지문자(`\ / : * ? " < > |`) 제거·trim, 비면 `output`으로 대체, `.wav` 자동 부여.
- 저장 폴더: 기본값 = 프로젝트 `output/` 절대경로. 입력 경로가 없으면 `os.makedirs(exist_ok=True)`로 생성.
- 충돌 시: `name.wav`가 있으면 `name (2).wav`, `name (3).wav` … 자동 증가(덮어쓰기 방지).
- 디스크에 저장 후 그 경로를 오디오 컴포넌트에 전달(브라우저 재생/다운로드도 동일 파일명).

## 크로스플랫폼 의존성

`requirements.txt`를 환경 마커로 분기:
```
torch==2.5.1+cpu ; sys_platform == "win32"
torch==2.5.1     ; sys_platform == "darwin"
--extra-index-url https://download.pytorch.org/whl/cpu   # win에서 +cpu 휠 해결용(맥은 PyPI 사용)
kokoro, soundfile, numpy, gradio
# 일본어
lemon-pyopenjtalk-prebuilt ; sys_platform == "win32"
pyopenjtalk                ; sys_platform == "darwin"   # 맥은 clang으로 자체 빌드 가능(Xcode CLT 필요)
fugashi, unidic-lite, jaconv, mojimoji
```
- 윈도우: 검증 완료 경로.
- 맥: 코드로 준비하되 **동업자 맥에서 첫 실행 테스트 필요**(torch·pyopenjtalk 빌드 가능 여부). 실패 시 대안(prebuilt 맥 휠 확인 또는 MeloTTS) 강구.

## 설치·실행 스크립트 (더블클릭 수준)
- `setup-windows.bat`, `setup-mac.command`: venv 생성 + `pip install -r requirements.txt`.
- `run-windows.bat`, `run-mac.command`: venv 파이썬으로 `app.py` 실행(브라우저 자동 오픈).
- 맥 `.command`는 실행권한 필요(`chmod +x`) — README에 안내.

## 배포 (비공개 GitHub)
- `gh repo create <name> --private --source . --push` 로 생성·업로드(인증 필요).
- 동업자: 저장소에서 ZIP 다운로드 또는 clone → 셋업 스크립트 1회 실행 → 실행 스크립트로 사용.
- README에 맥·윈도우 단계별(한국어) 안내.

## 검증 계획
- 윈도우: `app.py` 실행 → 브라우저 로드 → 영어·일본어 각 1회 생성, 지정한 이름·폴더에 .wav 저장 확인, 재생 가능 확인. CLI(`tts.py`) 회귀 확인.
- 코어 리팩터 후 기존 `tts.py` 동작 동일함 확인(영/일 재생성).
- 맥: 동업자 환경에서 첫 실행 테스트(별도).

## 범위 밖 (YAGNI)
- 목소리 섞기, MP3 자동 변환, 자막(.srt), 번역, 음성 복제, 클라우드 호스팅, 실행파일(.exe/.app) 패키징.
