# 외국어 영상용 TTS (일본어 · 영어)

무료 오픈소스 모델 **Kokoro**(Apache 2.0)로 일본어·영어 영상 내레이션 음성을 만듭니다.
**GPU 없이 CPU에서 동작**하고, 두 가지 방식으로 쓸 수 있습니다:

| 방식 | 대상 | 설명 |
|------|------|------|
| 🖥️ **웹 UI** (`app.py`) | 누구나(비개발) | 브라우저에서 클릭·드롭다운으로 생성 |
| ⌨️ **CLI 일괄 처리** (`tts.py`) | 대량 작업 | 폴더에 대본 넣고 한 번에 변환 |

> ✅ Windows(Python 3.11, i7-1260P)에서 영어·일본어 생성·발음 검증 완료. 맥은 동일 코드로 준비됨(첫 실행 테스트 권장).

---

## 🚀 빠른 시작 — 설치 한 번 + 실행 (더블클릭)

압축을 푼 폴더에서 **OS에 맞는 파일 하나만 더블클릭**하면 됩니다. 첫 실행 때 필요한 것을 자동으로 설치한 뒤 브라우저가 열립니다(이후엔 바로 실행).

### 윈도우
- **`START-Windows.bat` 더블클릭** — 그게 전부입니다.
  - 처음엔 파이썬 3.11 + 라이브러리를 자동 설치합니다(몇 분, 인터넷 필요).
  - 파이썬이 없으면 자동 설치를 시도합니다(winget). 자동 설치가 안 되면 안내대로
    [python.org 3.11](https://www.python.org/downloads/release/python-3119/)에서 한 번 설치
    (설치 화면에서 **"Add python.exe to PATH" 체크**) 후 다시 더블클릭하세요.

### 맥
1. (처음 한 번) **`START-Mac.command` 우클릭 → 열기** → 뜨는 창에서 **열기** 클릭.
   - 인터넷에서 받은 앱이라 나오는 안전 확인입니다. **두 번째부터는 그냥 더블클릭**하면 됩니다.
   - 파이썬 3.11이 없으면 안내가 나옵니다 →
     [python.org 3.11 (macOS)](https://www.python.org/downloads/release/python-3119/) 설치
     (또는 `brew install python@3.11`) 후 다시 열기.

> 압축은 맥 기본 압축 해제(더블클릭)로 풀면 **실행 권한이 유지**되어 `chmod` 없이 바로 됩니다.
> 혹시 더블클릭 시 텍스트로만 열리면, 터미널에서 `chmod +x START-Mac.command` 한 번 후 다시 시도하세요.

> 처음 실행 시 모델(~327MB)·발음 데이터가 자동 다운로드됩니다(한 번만, 인터넷 필요).

### 웹 UI 사용법
브라우저 화면에서:
- **언어** (영어 미국/영국, 일본어) → 선택 시 **목소리** 목록이 자동으로 바뀜
- **목소리** 드롭다운 (영어 20종 / 일본어 5종) · **속도** 슬라이더 (0.5~2.0)
- **목소리 섞기**(체크): **목소리 2** 드롭다운과 **비율 슬라이더**가 나타남 →
  같은 언어의 두 목소리를 비율로 혼합 (왼쪽=목소리1, 오른쪽=목소리2)
- **대본**: 텍스트 붙여넣기 **또는** `.txt` 파일 업로드
- **포맷**: **WAV**(편집용 무손실) · **MP3**(공유) · FLAC · OGG
- **저장 폴더**: 아래 **[폴더 찾아보기…]**(창에서 클릭) · **[바탕화면]** · **[다운로드]** · **[기본 폴더]** 버튼으로 쉽게 고르거나 직접 입력
- **파일 이름** 지정 → **[음성 생성]** → 재생/다운로드, 지정 폴더에 저장. **[저장 폴더 열기]** 로 폴더를 바로 열 수 있음

---

## ⌨️ CLI 일괄 처리 (대량 작업용)

`scripts/en/`·`scripts/ja/` 에 `.txt`(UTF-8)를 넣고:
```bash
# 윈도우 (맥은 ./.venv/bin/python tts.py ...)
.\.venv\Scripts\python.exe tts.py                          # 전부 (WAV)
.\.venv\Scripts\python.exe tts.py --lang ja --format mp3   # 일본어만, MP3 로
.\.venv\Scripts\python.exe tts.py --lang en --voice am_michael --speed 1.1
# 목소리 섞기: 기본 목소리 70% + af_bella 30%
.\.venv\Scripts\python.exe tts.py --lang en --voice2 af_bella --mix 0.3
```
옵션: `--format {wav,mp3,flac,ogg}`(기본 wav), `--voice2 NAME`(믹스용 둘째 목소리),
`--mix 0~1`(voice2 비중, 기본 0.5=균등). `--voice2` 는 단일 언어(`--lang en|ja`)에서만.
→ `output/en/`·`output/ja/` 에 같은 이름으로 생성.

---

## 📦 동업자에게 전달하기 (개발자용)

git·GitHub 계정 없이 **압축파일 하나로** 전달합니다.
1. 코드를 바꿨다면 **먼저 커밋**하세요(`git archive` 는 커밋된 내용만 담음).
2. **`make-zip.bat` 더블클릭** → `dist\foreign-video-tts.zip` 생성
   (`.venv`·`.git`·캐시·생성된 음성은 자동 제외 — 가벼운 코드만).
3. 이 ZIP 을 동업자에게 전달(구글드라이브 / USB / 메신저).
4. 동업자는 압축을 풀고 위 **빠른 시작**대로 `START-Windows.bat`(맥은 `START-Mac.command`) 더블클릭.

---

## 🎬 영상으로 만들기
생성된 음성을 무료 편집기(**CapCut · DaVinci Resolve · Shotcut**)에 넣어 영상과 합치면 됩니다.
필요하면 앱에서 **포맷을 MP3로 골라 바로 저장**할 수 있습니다(별도 변환 프로그램 불필요).

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
- **(윈도우) 파이썬 자동 설치 실패**: [python.org 3.11](https://www.python.org/downloads/release/python-3119/)
  설치("Add python.exe to PATH" 체크) 후 `START-Windows.bat` 다시 더블클릭.
- **(맥) `.command` 가 안 열림**: `chmod +x START-Mac.command` 후 우클릭→열기.
- **저장 폴더 / 미리듣기**: 저장 폴더가 **홈 폴더 하위**면 브라우저 미리듣기까지 됩니다. 홈 밖(예: 다른 드라이브)이면 파일은 저장되지만 미리듣기가 안 뜰 수 있어요(파일은 정상). FLAC·OGG는 브라우저에 따라 미리듣기가 안 될 수 있으나 저장·다운로드는 정상.
- **수동 설치(스크립트 없이)**: `py -3.11 -m venv .venv` →
  `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` → `.\.venv\Scripts\python.exe app.py`
- **`HF_TOKEN` / `symlinks` 경고**: 무해합니다.
- **테스트**: `.\.venv\Scripts\python.exe tests\test_core.py` (순수 함수 검증).
