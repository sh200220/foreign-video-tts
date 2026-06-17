# 외국어 영상용 TTS (일본어 · 영어)

무료 오픈소스 모델 **Kokoro**(Apache 2.0)로 일본어·영어 영상 내레이션 음성을 만드는 작업 폴더입니다.
대본 텍스트(.txt)를 넣고 스크립트 한 번 실행하면 음성(.wav)이 나옵니다. GPU 없이 CPU에서 동작합니다.

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

PowerShell에서 이 폴더(`C:\Users\sh200\Desktop\TTS`)에 들어간 뒤:

```powershell
# 1) 전용 가상환경 만들기 (다른 파이썬 환경과 분리)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) 의존성 설치
pip install -r requirements.txt
```

> 처음 실행 시 모델(약 300MB)이 자동으로 한 번 다운로드됩니다.
>
> 만약 영어에서 `espeak` 관련 오류가 나면 [espeak-ng](https://github.com/espeak-ng/espeak-ng/releases) 를 설치하세요(무료). 최신 버전은 보통 자동 포함되어 추가 설치가 필요 없습니다.

---

## 2. 사용법

1. `scripts/en/` 또는 `scripts/ja/` 에 대본을 `.txt`(UTF-8)로 저장합니다.
   - **문장이나 문단마다 줄바꿈**을 넣으면 더 자연스럽게 끊어 읽습니다.
2. 가상환경을 켠 상태에서 실행:

```powershell
python tts.py              # en, ja 폴더 전부 처리
python tts.py --lang ja    # 일본어만
python tts.py --lang en --voice am_michael --speed 1.1   # 목소리·속도 지정
```

3. `output/` 폴더에 `.wav` 파일이 생성됩니다.

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
대본(.txt) → python tts.py → output/*.wav → 영상 편집기에서 영상+음성 합치기
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

## 5. 일본어 설치가 막힐 때 (대안: MeloTTS)

Windows에서 일본어 의존성 설치가 실패하면, 같은 폴더 구조를 유지한 채 엔진만 **MeloTTS**(MIT)로 교체할 수 있습니다.
필요하시면 알려주세요 — `tts.py`의 MeloTTS 버전을 안내해 드립니다.
