# 외국어 영상용 TTS (일본어 · 영어)

무료 오픈소스 모델 **Kokoro**(Apache 2.0)로 일본어·영어 영상 내레이션 음성을 만듭니다.
**GPU 없이 CPU에서 동작**하고, 두 가지 방식으로 쓸 수 있습니다:

| 방식 | 대상 | 설명 |
|------|------|------|
| 🖥️ **웹 UI** (`app.py`) | 누구나(비개발) | 브라우저에서 클릭·드롭다운으로 생성 |
| ⌨️ **CLI 일괄 처리** (`tts.py`) | 대량 작업 | 폴더에 대본 넣고 한 번에 변환 |

> ✅ Windows(Python 3.11, i7-1260P)에서 영어·일본어 생성·발음 검증 완료. macOS는 동일 코드로 준비됨(첫 실행 테스트 권장 — 아래 참고).

---

## 🚀 빠른 시작 — 웹 UI (추천)

### 윈도우
1. `setup-windows.bat` **더블클릭** (처음 한 번, 설치 — 몇 분 소요)
2. `run-windows.bat` **더블클릭** → 잠시 후 브라우저가 자동으로 열립니다

### 맥
1. (처음 한 번) 터미널에서 이 폴더로 가서 실행 권한 부여:
   ```bash
   chmod +x setup-mac.command run-mac.command
   ```
2. `setup-mac.command` **더블클릭** (처음 한 번, 설치)
   - "확인되지 않은 개발자" 경고 시: 파일 **우클릭 → 열기**
3. `run-mac.command` **더블클릭** → 브라우저가 열립니다

> 처음 실행 시 모델(~327MB)·발음 데이터가 자동 다운로드됩니다(한 번만, 인터넷 필요).

### 웹 UI 사용법
브라우저 화면에서:
- **언어** (영어 미국/영국, 일본어) → 선택 시 **목소리** 목록이 자동으로 바뀜
- **목소리** 드롭다운 (영어 20종 / 일본어 5종)
- **속도** 슬라이더 (0.5~2.0, 1.0=보통)
- **대본**: 텍스트 붙여넣기 **또는** `.txt` 파일 업로드
- **파일 이름** + **저장 폴더** 지정 → [🔊 생성하기] → 재생/다운로드, 지정 폴더에 `.wav` 저장

---

## ⌨️ CLI 일괄 처리 (대량 작업용)

`scripts/en/`·`scripts/ja/` 에 `.txt`(UTF-8)를 넣고:
```bash
# 윈도우
.\.venv\Scripts\python.exe tts.py            # 전부
.\.venv\Scripts\python.exe tts.py --lang ja  # 일본어만
.\.venv\Scripts\python.exe tts.py --lang en --voice am_michael --speed 1.1
# 맥은 ./.venv/bin/python tts.py ...
```
→ `output/en/`·`output/ja/` 에 같은 이름의 `.wav` 생성.

---

## 🎬 영상으로 만들기
생성된 `.wav` 를 무료 편집기(**CapCut · DaVinci Resolve · Shotcut**)에 넣어 영상과 합치면 됩니다.
MP3가 필요하면 [ffmpeg](https://ffmpeg.org/): `ffmpeg -i input.wav output.mp3`

---

## 📜 라이선스 (상업적 사용)
- **Kokoro 모델**: Apache 2.0 — 상업적 사용 가능. 실제 음성은 Kokoro 가중치에서 생성.
- **일본어 발음 의존성**(pyopenjtalk, fugashi 등): 발음 변환용, MIT·BSD 계열. 프리셋 목소리(음성 복제 아님).
- 고위험·대규모 상업 용도면 각 패키지 라이선스를 한 번 더 직접 확인 권장.

---

## 🔧 문제 해결
- **(윈도우) `import torch ... c10.dll WinError 1114`**: 최신 torch가 안 맞습니다. 고정 버전 재설치:
  `.\.venv\Scripts\python.exe -m pip install "torch==2.5.1+cpu" --index-url https://download.pytorch.org/whl/cpu`
  (이미 `requirements.txt`에 반영됨 — torch를 임의로 올리지 마세요.)
- **저장 폴더 / 미리듣기**: 저장 폴더가 **홈 폴더 하위**면 브라우저 미리듣기까지 됩니다. 홈 밖(예: 다른 드라이브)이면 파일은 저장되지만 브라우저 미리듣기가 안 뜰 수 있어요(파일은 정상).
- **(맥) 일본어 첫 실행**: 맥용 prebuilt 일본어 엔진(`pyopenjtalk-prebuilt`)으로 설정돼 있으나, 맥에서 한 번도 실측하지 못했습니다. 일본어가 안 되면 알려주세요(대안 적용).
- **(맥) `.command` 가 안 열림**: `chmod +x *.command` 후 우클릭→열기.
- **`HF_TOKEN` / `symlinks` 경고**: 무해합니다.
