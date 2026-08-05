# 한국어 TTS(Supertonic) + 업그레이드 3종 — 설계 스펙

날짜: 2026-08-05
상태: 사용자 승인됨 (엔진 = Supertonic, 기능 = 대화 모드 · 인라인 쉼 태그 · 자막 줄 규격화)

## 배경

- 현재 앱은 Kokoro-82M(Apache 2.0)으로 영어(미국/영국)·일본어를 지원한다.
- **Kokoro는 한국어를 지원하지 않는다** → 한국어는 별도 엔진을 붙여야 한다.
- 제약: 상업적 사용 가능 라이선스, CPU 전용, Windows(동업자 PC 포함)·macOS, 오프라인 동작(첫 모델 다운로드 1회만 인터넷).

## 엔진 선정: Supertonic 3 (Supertone)

- `pip install supertonic`. ONNX Runtime 기반 → **torch 2.5.1+cpu 핀과 완전 무관**(충돌 없음).
- 한국어 포함 31개 언어, 프리셋 목소리 남5(M1~M5)·여5(F1~F5), 44.1kHz 출력, 속도 0.7~2.0.
- 첫 실행 시 HuggingFace에서 모델 자동 다운로드(~99M 파라미터, Kokoro와 동일 패턴).
- 라이선스: 예제 코드 MIT, 모델 OpenRAIL-M(상업 사용 가능 + 불법·유해 용도 금지 조항).
  구현 시 LICENSE 원문을 확인해 README에 요약 기록한다.
- 탈락 후보: MeloTTS(한국어 여성 1명뿐, Windows 설치 험난, torch 의존),
  유료 API(오프라인 불가·비용), edge-tts(상업 이용 약관 회색지대).

## 기능 1 — 한국어 TTS

### 코어 (kokoro_core.py + supertonic_engine.py 신규)

- `supertonic_engine.py`(신규 소형 모듈): TTS 인스턴스·voice style 캐시 + `synth_line(text, voice, speed) -> np.float32[]`
  + `SAMPLE_RATE = 44100`. lazy import(미설치 시 안내 메시지를 담은 RuntimeError).
- `kokoro_core.LANGS`에 `"한국어": {code: "k", default_voice: "F1", engine: "supertonic"}` 추가.
  기존 항목은 engine: "kokoro". `VOICES["k"] = [F1..F5, M1..M5]`.
- `synthesize*()`는 lang_code로 엔진 분기. 반환 형식 `(audio, sr[, segments])` 불변 —
  app.py/tts.py는 반환된 sr을 그대로 쓰므로 44.1kHz가 자연 흡수된다.
- 속도: 한국어는 0.7 미만 입력 시 0.7로 클램프(도움말에 명시).
- `blend_voices()`(목소리 섞기)는 Kokoro 전용 → code "k"이면 ValueError.

### UI (app.py)

- 언어 드롭다운에 "한국어" 추가. 한국어 선택 시 **목소리 섞기 체크박스 숨김**(값도 무시).
- `PREVIEW_TEXT["k"]` 한국어 샘플 문장, `CPS["k"]`는 구현 중 실측값.
- supertonic 미설치 시: 생성 시점에 "pip install -r requirements.txt 재실행" 안내 오류.

### CLI (tts.py)

- `FOLDER_LANG["ko"] = ("k", "F1")`, `--lang` choices에 ko 추가, `scripts/ko/`·`output/ko/` 생성
  (+ sample_intro.txt).

### 배포

- requirements.txt에 `supertonic` 추가(ASCII 유지). 설치방법.txt·README에
  "한국어 첫 생성 시 모델 자동 다운로드(인터넷 1회)" 안내.

## 기능 2 — 화자별 대화 모드

- 대본 카드에 "대화 모드" 체크박스 + (켜면 표시) 화자 지정 텍스트박스. 한 줄에 `이름=목소리`:

  ```
  A=af_heart
  B=am_michael
  ```

- 대본 줄이 `이름: 내용` / `이름： 내용`(전각 콜론 허용)이고 **이름이 등록돼 있을 때만**
  해당 목소리로 합성. 등록 안 된 접두사(`참고:` 등)는 오탐 없이 통째로 기본 목소리로 읽는다.
- 자막(.srt)에는 접두사를 뺀 말한 내용만 기록.
- 검증: 지정한 목소리가 현재 언어 목록에 없으면 목록을 보여주는 오류.
- 대화 모드 ON이면 목소리 섞기는 무시(도움말에 명시). CLI에는 넣지 않는다(YAGNI).
- 설정(`~/.foreign-video-tts.json`)에 체크박스·매핑 저장.

## 기능 3 — 인라인 쉼 태그

- 문법: `[쉼:1.5]` — 초 단위 소수 허용, 0~10초로 클램프. 정규식에 맞는 태그만 처리하고
  그 외(`[쉼:abc]`)는 일반 텍스트로 그대로 읽는다. 전각 콜론 허용.
- 줄 중간: 태그 앞뒤를 나눠 합성하고 사이에 무음 삽입. 자막 세그먼트는
  "그 줄에서 말이 시작~끝나는 구간"(내부 쉼 포함, 줄 가장자리 쉼은 제외).
- 줄 전체가 태그뿐이면: 자막 없는 순수 무음(장면 전환용).
- 엔진 무관(텍스트 레벨) — 영어/일본어/한국어 모두 동작.

## 기능 4 — 자막 줄 규격화

- 저장 카드에 슬라이더 "자막 한 줄 최대 글자 수" (0=제한 없음(기본), 범위 0~60,
  도움말에 영어 42 / 한·일 20~24 권장 표기). 설정 저장.
- 코어에 순수 함수 `split_segments_for_srt(segments, max_chars)`:
  초과 세그먼트를 공백(영/한) → 문장부호(、。！？!?…,) → 글자 수 순의 경계에서 나누고,
  시간은 조각 글자 수 비례로 배분해 여러 SRT 블록 생성.

## 공통 리팩터

- `synthesize_segments()`를 **줄 단위 렌더 루프**로 재구성(모든 경로 통일):
  줄마다 → (대화 모드면 화자 결정) → 쉼 태그 분해 → 엔진별 한 줄 합성 → 무음 삽입 → 타이밍 기록.
  Kokoro도 pipe를 줄 단위로 호출(현재도 split_pattern으로 줄 분리되므로 결과 동일).
- `synthesize()`는 위 함수의 오디오만 반환하는 래퍼로 단순화.
- `SAMPLE_RATE`(24000)는 Kokoro 상수로 유지 — 하위 호환.

## 오류 처리

- supertonic 미설치/모델 다운로드 실패 → 원인+해결(재설치, 인터넷 연결) 안내 메시지.
- 대화 모드 매핑 문법 오류/미등록 목소리 → 어느 줄이 문제인지 알려주는 gr.Error.
- 배치(.txt 여러 개)에서는 기존처럼 파일 하나 실패해도 나머지 계속.

## 테스트 (tests/test_core.py 스타일 — 모델·네트워크 불필요한 순수 로직)

- 쉼 태그 파싱: 위치·초·클램프·잘못된 형식 무시·태그 단독 줄.
- 화자 매핑 파싱: `이름=목소리` 파싱, `이름:` 매칭(전각 포함), 미등록 접두사 통과.
- `split_segments_for_srt`: 경계 선택, 시간 비례 배분, 0=무제한.
- 속도 클램프(한국어 0.7), `blend_voices("k", ...)` ValueError, LANGS/VOICES 무결성.
- 실제 한국어 합성 e2e는 수동 확인(기존 관례).

## 리스크

1. **supertonic 의존성 충돌**: 구현 1단계에서 실제 .venv에 설치해 기존 핀
   (torch 2.5.1+cpu, gradio 6.18, numpy, macOS numpy 1.26.4)과 공존 검증.
   macOS에서 numpy 상충 시: 마커로 분리 설치 또는 macOS 한국어 미지원을 명시하고 진행.
2. **Supertonic 목소리 상세**(정확한 프리셋 이름·개수)는 설치 후 API로 확정해 VOICES에 반영.
3. 긴 대본 CPU 속도: Supertonic은 Kokoro보다 빠른 것으로 알려짐 — 실측해 CPS에 반영.
