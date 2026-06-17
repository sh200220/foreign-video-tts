# 외국어 영상용 TTS (일본어 · 영어)

무료 오픈소스 모델 **Kokoro**(Apache 2.0)로 일본어·영어 영상 내레이션 음성을 만드는 작업 폴더입니다.
대본 텍스트(.txt)를 넣고 스크립트 한 번 실행하면 음성(.wav)이 나옵니다. **GPU 없이 CPU에서 동작**합니다.

> ✅ 이 환경(Windows 11, Python 3.11, i7-1260P)에서 영어·일본어 모두 **생성 검증 완료**.

---

## 폴더 구조

```
TTS/
├── scripts/          ← 대본 텍스트(.txt)를 여기에 넣습니다
│   ├── en/           ← 영어 대본
│   └── ja/           ← 일본어 대본
├── output/           ← 생성된 음성(.wav)이 여기에 나옵니다
│   ├── en/
│   └── ja/
├── tts.py            ← 실행 스크립트
├── requirements.txt
└── README.md
```

`scripts/ja/intro.txt` 를 넣고 실행하면 → `output/ja/intro.wav` 가 만들어집니다.

---

## 1. 설치 (처음 한 번만)

PowerShell에서 이 폴더(`C:\Users\sh200\Desktop\TTS`)로 이동한 뒤:

```powershell
# 1) 전용 가상환경 생성
python -m venv .venv

# 2) 의존성 설치 (torch CPU + Kokoro + 일본어 지원이 한 번에 설치됩니다)
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

> **처음 실행 시 자동 다운로드** 되는 것들 (한 번만): Kokoro 모델(~327MB), 영어 발음용 `en_core_web_sm`, 일본어용 pyopenjtalk 사전. 인터넷 연결 필요.

설치는 끝났습니다. (`requirements.txt`가 torch CPU 버전 고정과 일본어 의존성까지 모두 처리합니다.)

---

## 2. 사용법

1. `scripts/en/` 또는 `scripts/ja/` 에 대본을 `.txt`(UTF-8)로 저장합니다.
   - **문장이나 문단마다 줄바꿈**을 넣으면 더 자연스럽게 끊어 읽습니다.
2. 실행 (가상환경을 따로 활성화할 필요 없이 venv 파이썬을 직접 호출):

```powershell
.\.venv\Scripts\python.exe tts.py              # en, ja 폴더 전부 처리
.\.venv\Scripts\python.exe tts.py --lang ja    # 일본어만
.\.venv\Scripts\python.exe tts.py --lang en --voice am_michael --speed 1.1
```

3. `output/` 폴더에 `.wav` 파일이 생성됩니다.

> 매번 `.\.venv\Scripts\python.exe` 를 치기 번거로우면 `.\.venv\Scripts\Activate.ps1` 로 가상환경을 활성화한 뒤 `python tts.py` 만 써도 됩니다.
> (활성화 시 "스크립트 실행이 차단됨" 오류가 나면: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 한 번 실행)

### 옵션
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--lang` | `en` / `ja` / `all` | `all` |
| `--voice` | 목소리 지정 (단일 언어일 때만) | 언어별 기본값 |
| `--speed` | 말하기 속도 배율 (0.9 느리게, 1.2 빠르게) | `1.0` |

전체 처리 시 기본 목소리를 바꾸려면 `tts.py` 상단의 `LANG_CONFIG` 를 수정하세요.

### 목소리 예시
- **영어(미국)** 여성: `af_heart`(기본), `af_bella`, `af_nicole` / 남성: `am_michael`, `am_fenrir`, `am_puck`
- **일본어** 여성: `jf_alpha`(기본), `jf_gongitsune`, `jf_nezumi` / 남성: `jm_kumo`

전체 목록은 [Kokoro 모델 카드](https://huggingface.co/hexgrad/Kokoro-82M)의 VOICES 참고.

---

## 3. 영상으로 만들기

```
대본(.txt) → tts.py 실행 → output/*.wav → 영상 편집기에서 영상+음성 합치기
```

무료 편집기: **CapCut**, **DaVinci Resolve**, **Shotcut** 등. `.wav`를 그대로 불러오면 됩니다.
MP3가 필요하면 [ffmpeg](https://ffmpeg.org/)로 변환: `ffmpeg -i output/en/intro.wav output/en/intro.mp3`

---

## 4. 라이선스 (상업적 사용)

- **Kokoro 모델**: Apache 2.0 — **상업적 사용 가능**. 실제 음성은 Kokoro 가중치에서 생성됩니다.
- **일본어 발음 의존성**(`pyopenjtalk`, `fugashi`, `unidic-lite` 등): 텍스트→발음 변환에만 쓰이며 코드/사전은 MIT·BSD 계열입니다.
- 음성 자체에는 사람 목소리 복제가 포함되지 않은 **프리셋 목소리**입니다.

> 고위험·대규모 상업 용도라면, 사용하는 패키지들의 라이선스를 한 번 더 직접 확인하시길 권장합니다.

---

## 5. 문제 해결 (Troubleshooting)

- **`import torch` 에서 `c10.dll ... WinError 1114` 오류**
  최신 torch(2.12.0)가 이 PC에서 초기화에 실패합니다. **안정 버전으로 고정**하세요(이미 `requirements.txt`에 반영됨):
  ```powershell
  .\.venv\Scripts\python.exe -m pip install "torch==2.5.1+cpu" --index-url https://download.pytorch.org/whl/cpu
  ```
  → **torch를 임의로 최신으로 올리지 마세요.**

- **`symlinks ... degraded` 경고**: 무해합니다. 거슬리면 Windows "개발자 모드"를 켜면 사라집니다.

- **`HF_TOKEN` 경고**: 무해합니다(다운로드 속도 제한 안내일 뿐).

- **일본어 설치가 정말 안 될 때 (심층 대안)**: 본 프로젝트는 미리빌드 휠(`lemon-pyopenjtalk-prebuilt`)로 컴파일러 문제를 회피합니다. 그래도 막히면 일본어 엔진만 **MeloTTS**(MIT)로 교체할 수 있습니다 — 필요 시 요청하세요.
