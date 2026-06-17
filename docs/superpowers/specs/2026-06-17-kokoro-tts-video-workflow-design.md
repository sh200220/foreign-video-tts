# 외국어 영상용 TTS 워크플로우 설계 (Kokoro)

- 작성일: 2026-06-17
- 상태: 승인됨 (사용자 승인 후 구현)

## 목표

외국인 대상 영상에 넣을 **일본어·영어 내레이션 음성**을 무료 오픈소스 TTS로 생성한다.
대본(.txt)을 넣고 스크립트를 실행하면 음성(.wav)이 나오는, 반복 사용 가능한 로컬 워크플로우를 만든다.

## 제약 / 결정 사항

| 항목 | 결정 | 이유 |
|------|------|------|
| 용도 | 상업적·비즈니스 | 라이선스가 허용적(MIT/Apache)인 모델만 사용 |
| 입력 | 사용자가 JA/EN 대본 직접 준비 | 번역 단계 불필요, 순수 TTS만 |
| 하드웨어 | Intel GPU만(NVIDIA 없음) → CPU 실행 | 가볍고 CPU에서 빠른 모델 선택 |
| 기술 수준 | 파이썬·명령어 OK | pip 설치 + 스크립트 실행 방식 |
| 선택 모델 | **Kokoro-82M** (Apache 2.0) | 최상 품질/경량, 깨끗한 상업 라이선스, EN+JA 지원 |
| 백업 모델 | MeloTTS (MIT) | JA 의존성 설치 문제 시 동일 워크플로우로 교체 |

XTTS-v2 등 고품질 모델은 **비상업 라이선스**라 제외.
프리셋 목소리만 사용(상업 무료로는 음성 복제 불가).

## 아키텍처

단일 배치 스크립트 + 폴더 규약. 외부 서비스·서버 없음(전부 로컬).

```
scripts/<lang>/*.txt  --(tts.py)-->  output/<lang>/*.wav  -->  영상 편집기
```

### 폴더 구조
```
TTS/
├── scripts/{en,ja}/      # 입력 대본(.txt, UTF-8)
├── output/{en,ja}/       # 출력 음성(.wav, 24kHz)
├── tts.py                # 배치 생성 스크립트
├── requirements.txt      # kokoro, soundfile, misaki[ja], numpy
└── README.md             # 한글 사용법
```

### 컴포넌트: `tts.py`
- **역할:** `scripts/<lang>` 의 모든 `.txt`를 읽어 언어별 목소리로 음성 생성 후 `output/<lang>`에 동일 이름 `.wav` 저장.
- **인터페이스(CLI):** `--lang {en,ja,all}`, `--voice <name>`, `--speed <float>`.
- **언어 매핑:** `LANG_CONFIG` 에서 폴더명 → (Kokoro lang_code, 기본 목소리). en→('a', af_heart), ja→('j', jf_alpha).
- **의존:** `kokoro.KPipeline`(합성), `soundfile`(저장), `numpy`(조각 이어붙이기).
- **처리:** 긴 대본은 줄바꿈(`\n+`) 기준으로 분할 생성 후 numpy로 concat. 오디오는 torch 텐서/배열 모두 numpy로 변환.

## 데이터 흐름
1. 사용자가 대본을 `scripts/<lang>/name.txt`로 저장.
2. `python tts.py` 실행 → 언어별 `KPipeline` 1회 로드.
3. 각 파일 합성 → `output/<lang>/name.wav` 저장, 길이(초) 출력.
4. 사용자가 `.wav`를 무료 편집기(CapCut/DaVinci/Shotcut)에서 영상과 합침.

## 예외 처리
- kokoro 미설치 → 설치 안내 후 종료(코드 1).
- `--voice` + `--lang all` 동시 사용 → 언어별 목소리 충돌 안내 후 종료(코드 2).
- 빈 텍스트/없는 폴더 → 건너뛰고 명확한 메시지.
- 개별 파일 합성 오류 → 해당 파일만 메시지 출력하고 다음 파일로 계속.

## 검증
- 가상환경(.venv)에 의존성 설치.
- 샘플 대본(en/ja 각 1개)으로 스모크 테스트 → `output/`에 재생 가능한 `.wav` 생성 확인.

## 라이선스 메모
- Kokoro 가중치 Apache 2.0(상업 가능). 일본어 G2P 의존성(pyopenjtalk/fugashi/unidic-lite)은 발음 변환용이며 MIT·BSD 계열.
- 고위험 상업 용도 시 의존성 라이선스 직접 재확인 권장(README에 명시).

## 범위 밖 (YAGNI)
- 번역, 자막(.srt) 생성, 음성 복제, GUI, MP3 자동 변환(README에 ffmpeg 한 줄 안내로 충분).
