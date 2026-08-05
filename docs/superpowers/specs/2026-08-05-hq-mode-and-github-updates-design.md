# 고품질(Chatterbox) 모드 통합 + GitHub 업데이트 배포 — 설계 스펙

날짜: 2026-08-05
상태: 사용자 요청("고품질모드 통합 + 동업자가 GitHub에서 바로 받아 업데이트") 기반.
파일럿 A 실측: CPU RTF 6.4x, torch 2.6.0+cpu 이 PC에서 정상, 모델 캐시 ~3GB, sr=24000.

## 배경

- Chatterbox Multilingual(MIT, 23개 언어, exaggeration 감정 다이얼)을 앱의 "고품질 모드"로 통합한다.
- 의존성이 본 앱과 충돌(numpy<2, gradio 6.8, transformers 5.2, torch 2.6.0)하므로
  **별도 가상환경 `.venv-chatterbox`** 에 두고 **서브프로세스 워커**로 호출한다.
- 동업자 PC(RTX 2070)에서는 CUDA로 자동 가속, 이 PC에서는 CPU(느림, 배치용).
- 배포는 zip 전달 대신 **GitHub(private) + UPDATE 스크립트(git 기반)** 로 전환한다.

## 구조

### 워커 (chatterbox_worker.py — .venv-chatterbox 에서 실행)

- 시작 시 모델 1회 로드(장치: cuda 가능하면 cuda, 아니면 cpu), stdout 에 `{"ready":true,"device":...,"sr":24000}` 출력.
- 이후 stdin 한 줄 = 요청 JSON `{"text","lang","exaggeration","cfg","out"}` →
  합성해 out 경로에 wav 저장, stdout 한 줄 = `{"ok":true,"path","dur"}` 또는 `{"ok":false,"error"}`.
- stdin EOF 시 종료(부모 앱 종료와 수명 공유). 인코딩 UTF-8 고정.

### 엔진 (chatterbox_engine.py — 메인 venv)

- `SAMPLE_RATE=24000`, `LANGS={"ce":"en","cj":"ja","ck":"ko"}`, `VOICES=["기본 목소리"]`.
- 상주 워커 lazy 스폰/재스폰. `.venv-chatterbox` 없으면 "SETUP-고품질모드 실행" 안내 RuntimeError.
- `synth_line(text, lang, emotion)` → 워커 요청 → wav 파일 soundfile 로드 → float32 1-D.
- cfg_weight 자동 매핑: `cfg = clamp(0.5 - max(0, emotion-0.5) * 2/3, 0.3, 0.5)`
  (공식 권장: 감정↑ 시 cfg↓로 말 빨라짐 보정).
- 첫 사용 시 워커가 HF에서 모델(~3GB) 자동 다운로드 → ready 대기 타임아웃 30분.

### 코어 (kokoro_core.py)

- LANGS 추가: "영어 (고품질·감정)"=ce, "일본어 (고품질·감정)"=cj, "한국어 (고품질·감정)"=ck.
- `is_chatterbox(code)`, `supports_mix(code)`(kokoro 만 True), sample_rate_for(cb→24000).
- `synthesize_segments(..., emotion=None)` 파라미터 추가 → cb 경로에서만 사용(기본 0.5).
- cb 경로: 목소리 섞기 ValueError, voice_map(대화 모드) 무시(내장 목소리 1개), speed 무시.
- 쉼 태그·gap·자막·정규화·트림·장면분할은 기존 줄 단위 루프 그대로 동작.

### 앱 (app.py)

- 고품질 언어 선택 시: 속도 슬라이더 숨김 ↔ **감정 강도 슬라이더(0.25~0.8, 기본 0.5)** 표시,
  목소리 섞기 숨김(supports_mix), 통계줄에 "생성 시간 ≈ 오디오의 6~7배(CPU)/GPU는 실시간급" 안내.
- 미리듣기·생성 모두 emotion 전달. 설정(json)에 emotion 저장.
- 대본·기능 카드 등 나머지 UI 불변.

### 설치/배포 스크립트

- `SETUP-고품질모드.bat` / `SETUP-고품질모드.command`: `.venv-chatterbox` 생성,
  `nvidia-smi` 감지 시 torch/torchaudio 2.6.0+cu124, 아니면 +cpu 설치 후 chatterbox-tts==0.1.7.
  이미 있으면 빠르게 통과(멱등). 고품질 모드는 **옵션**(기본 앱은 이 환경 없이 그대로 동작).
- `UPDATE-Windows.bat` / `UPDATE-Mac.command`: git 없으면 설치 안내(winget 시도),
  `.git` 없으면(zip 출신 폴더) `git clone --no-checkout` 후 `.git` 이식,
  이후 매회 `git fetch + git reset --hard origin/main`(로컬 수정 덮어씀 — 소비자용, 문서화).
  비공개 저장소 인증은 Git Credential Manager 브라우저 로그인 1회(협업자 초대 필요, 문서화).
- START 스크립트의 기존 자동 보충 설치(requirements 프로브)가 업데이트 후 신규 의존성 처리.

## 테스트

- 순수: LANGS/코드 매핑, supports_mix, cfg 매핑 공식, cb blend ValueError, sample_rate.
- e2e(수동, 이 PC): ce/ck 각 1클립 + 쉼 태그 1회 — 워커 왕복·조립·자막 확인.
- UI 스모크: import app + 브라우저 확인.

## 남는 결정(사용자)

- 저장소 공개 여부: 공개 시 동업자 GitHub 계정·로그인 불필요(zip 다운로드/업데이트 무인증).
  기본 구현은 비공개+협업자 초대 흐름. 협업자 초대는 소유자만 가능(안내 문서에 절차 기재).
