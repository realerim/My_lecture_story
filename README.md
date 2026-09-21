# 학습 노트 (lecture-note)

Zoom 강의에 참여해 둔 상태로 다른 일을 하고 있어도, 백그라운드에서 **공유 화면이 바뀔
때마다 스크린샷을 찍고**, 그 구간 동안 **교수님이 하신 말씀을 음성 인식으로 받아 적은
뒤**, Claude로 강의 흐름에 맞게 정리해 **마크다운 노트 + 로컬 웹뷰어**로 보여주는
프로그램입니다.

> Zoom 개발자 계정이나 API 키는 필요 없습니다. Zoom 미팅에 참여한 컴퓨터의 화면과
> 오디오를 이 프로그램이 직접 지켜보는 방식입니다.

## 두 가지 사용 모드

1. **실시간 모드 (`record`)** — Zoom 미팅에 참여해 둔 상태에서 이 명령을 실행해 두면,
   화면 전환마다 스크린샷을 저장하고 오디오를 청크 단위로 전사합니다. 미팅이 끝나면
   `Ctrl+C`로 멈추면 최종 노트가 정리됩니다.
2. **녹화본 처리 모드 (`process`)** — 이미 가지고 있는 Zoom 녹화 파일(mp4 등)을 통째로
   넘기면 장면 전환 지점을 자동으로 찾아 스크린샷을 뽑고 전체 오디오를 전사해 동일한
   형식의 노트를 만듭니다.

두 모드 모두 결과물은 `data/sessions/<세션ID>/notes.md` 마크다운 파일과, `lecture-note
serve`로 띄우는 로컬 웹뷰어(`http://127.0.0.1:8000`)에서 동일하게 확인할 수 있습니다.
실시간 모드는 녹화 중에도 웹뷰어를 함께 켜 두면 5초마다 자동 새로고침되어, 다른 작업을
하다가도 지금까지 어디까지 진행됐는지 바로 볼 수 있습니다.

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

녹화본 처리 모드를 쓰려면 [ffmpeg](https://ffmpeg.org/)가 PATH에 있어야 합니다.

```bash
# macOS
brew install ffmpeg
# Ubuntu/Debian
sudo apt install ffmpeg
# Windows
winget install ffmpeg
```

Claude로 노트를 정리하고 싶다면(권장) 환경변수로 API 키를 설정하세요. 설정하지 않으면
자동으로 원문 전사만 담긴 노트가 만들어집니다.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## 빠른 테스트 (Zoom/마이크 설정 없이)

Zoom이나 오디오 루프백을 준비하지 않고도 파이프라인 전체(장면 전환 감지 → 전사 →
강의자료 매칭 → 노트 생성 → 웹뷰어)를 바로 확인할 수 있도록, 화면이 3번 바뀌는 가짜
강의 영상과 그에 맞는 강의자료 PDF를 만들어주는 스크립트를 넣어뒀습니다.

```bash
pip install -e .
python scripts/generate_demo.py demo   # ffmpeg, espeak-ng, 한글 폰트(fonts-noto-cjk) 필요
lecture-note process demo/lecture.mp4 --materials demo/slides.pdf --whisper-model tiny
lecture-note serve
```

`http://127.0.0.1:8000`에서 스크린샷 3장 + 정리된 텍스트가 나오면 정상 동작하는 것입니다.
실제로 이 저장소 안에서 위 과정을 실행해 장면 전환 감지·강의자료 매칭·노트 생성·웹뷰어
전부 동작을 확인했습니다(전사 모델 다운로드만 이 샌드박스의 네트워크 정책상 huggingface.co가
막혀 있어 직접 실행하지 못했고, 대신 나레이션 원문을 그대로 넣어 이후 단계를 검증했습니다 —
일반 인터넷이 되는 환경에서는 `lecture-note process`가 첫 실행 시 자동으로 모델을 받습니다).

## 실시간 모드: `lecture-note record`

1. Zoom 미팅에 평소처럼 참여하고, 발표자가 화면 공유를 시작합니다.
2. 같은 컴퓨터에서 아래 명령을 실행합니다.

   ```bash
   lecture-note record --title "자료구조 3주차"
   ```

3. (선택) 다른 터미널에서 웹뷰어를 띄워 진행 상황을 실시간으로 확인합니다.

   ```bash
   lecture-note serve
   # http://127.0.0.1:8000 접속
   ```

4. 강의가 끝나면 `record`를 실행한 터미널에서 `Ctrl+C`를 누릅니다. 캡처를 마무리하고,
   (API 키가 있다면) Claude로 섹션별 내용을 정리한 뒤 `notes.md`를 생성합니다.

### 오디오(교수님 목소리) 캡처 설정 — 가장 중요한 부분

`record`는 **시스템에 설정된 입력 장치**를 그대로 녹음합니다. 마이크만 녹음하면
Zoom을 통해 나오는 다른 참가자(교수님)의 목소리는 잡히지 않으므로, **스피커로 나가는
소리를 그대로 입력으로 받는 "루프백" 장치**를 준비해야 합니다.

| OS | 방법 |
|---|---|
| Windows | 소리 설정 → 녹음 탭에서 **"스테레오 믹스"** 활성화, 또는 [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) 설치 |
| macOS | 코어오디오는 루프백을 기본 지원하지 않으므로 [BlackHole](https://github.com/ExistentialAudio/BlackHole) 설치 후, 오디오 MIDI 설정에서 스피커+BlackHole을 묶은 "멀티출력장치"를 만들어 기본 출력으로 설정 |
| Linux (PulseAudio/PipeWire) | 출력 장치의 **"Monitor"** 소스를 입력 장치로 선택 (pavucontrol에서 확인 가능) |

사용 가능한 입력 장치 목록은 다음으로 확인합니다.

```bash
lecture-note list-devices
```

원하는 장치 이름의 일부를 `--audio-device`로 넘기면 됩니다.

```bash
lecture-note record --title "자료구조 3주차" --audio-device "BlackHole"
```

### 화면 감지 민감도 조절

- `--interval` (기본 2초): 화면을 확인하는 주기.
- `--phash-threshold` (기본 6): 값이 낮을수록 작은 변화에도 새 스크린샷을 찍습니다
  (교수님이 커서만 움직여도 캡처되는 게 싫다면 값을 높이세요).
- `--monitor` (기본 1): 여러 모니터를 쓴다면 Zoom 화면 공유가 떠 있는 모니터 번호로
  지정하세요.

## 녹화본 처리 모드: `lecture-note process`

Zoom 클라우드/로컬 녹화 파일을 그대로 넘깁니다.

```bash
lecture-note process ~/Downloads/zoom_lecture.mp4 --title "자료구조 3주차"
```

- `--scene-threshold` (기본 0.01, 0~1): 낮출수록 더 미세한 화면 변화도 캡처합니다. 정지된
  발표 자료 화면은 카메라 촬영 영상보다 장면 전환 점수가 훨씬 낮게 나와(실측 기준 전환
  시 0.01~0.08, 평상시 0.0005 이하) 기본값을 낮게 잡았습니다. 화면이 너무 자주/적게
  잡히면 이 값을 조절하세요.
- 오디오 전체를 한 번에 전사하므로 영상 길이에 따라 시간이 걸릴 수 있습니다
  (`--whisper-model tiny`나 `small`로 속도를 높일 수 있습니다).

## 미리 가진 강의 자료(PDF) 참고시키기

수업 전에 슬라이드나 교재 PDF가 있다면 `--materials`로 넘겨주세요. `record`/`process`
둘 다 지원합니다.

```bash
lecture-note record --title "자료구조 3주차" --materials ~/Downloads/slides.pdf
lecture-note process lecture.mp4 --materials ~/Downloads/slides.pdf ~/Downloads/textbook.pdf
```

캡처된 화면 스크린샷과 가장 비슷한 자료 페이지를 자동으로 찾아, Claude가 그 페이지의
원문 텍스트까지 참고해 설명을 보강합니다(정확한 수치·용어 등 화면만으로는 놓치기 쉬운
내용 보완). 일치하는 페이지를 참고했을 때만 노트 끝에 `(참고: 강의자료 N페이지)`가
붙습니다. PPT(.pptx) 파일은 PDF로 내보낸 뒤 사용하세요.

> 정리된 설명은 섹션마다 불릿 3~4개, 한 문장씩으로 길이를 제한합니다. 화면 전환이
> 잦은 강의라도 각 섹션이 장황해져 읽기 어려워지지 않도록 하기 위함입니다.

## 노트 형식

각 섹션은 "화면이 바뀐 시점"을 기준으로 나뉘며, 다음을 포함합니다.

- 시간 구간 (`[00:03:10 ~ 00:07:45]`)
- 그 구간에 떠 있던 화면의 스크린샷
- Claude가 화면 내용 + 음성 전사를 바탕으로 정리한 설명 (API 키가 없으면 원문 전사)
- (정리본이 있는 경우) 원문 전사는 접을 수 있는 `<details>` 블록으로 함께 보존

```
data/sessions/20260921-143000_자료구조-3주차/
    notes.md              ← 완성된 마크다운 노트
    screenshots/           ← 캡처된 스크린샷
    meta.json
    screen_events.jsonl
    transcript.jsonl
    organized.json         ← Claude 정리본 (있는 경우)
    materials/              ← --materials로 넘긴 PDF를 페이지별로 저장 (있는 경우)
```

## 명령어 요약

| 명령 | 설명 |
|---|---|
| `lecture-note record` | 실시간 화면/음성 캡처 시작 (Ctrl+C로 종료 및 노트 생성) |
| `lecture-note process <영상파일>` | 녹화 파일을 한 번에 처리 |
| `lecture-note serve` | 로컬 웹뷰어 실행 (`--host`, `--port`) |
| `lecture-note list-devices` | 사용 가능한 오디오 입력 장치 목록 |

`record`/`process`는 공통으로 `--no-claude`(Claude 정리 단계를 끄고 원문 전사만 남김),
`--whisper-model`(tiny/base/small/medium/large-v3), `--language`(기본 `ko`),
`--materials`(참고할 강의 자료 PDF)를 지원합니다.

## 개발 / 테스트

핵심 로직(화면 변경 감지, 구간 병합, 마크다운 생성)은 실제 화면·마이크·Zoom 없이도
유닛 테스트로 검증됩니다.

```bash
pip install -e ".[dev]"
pytest
```

실시간 화면 캡처(`mss`)와 오디오 녹음(`sounddevice`)은 실제 디스플레이/오디오 장치가
있는 사용자 PC에서만 동작합니다 — 이 두 기능 자체는 저장소를 만든 환경(디스플레이·
마이크가 없는 서버)에서는 실행해 테스트할 수 없었고, 로컬에서 직접 실행해 확인해야
합니다. `notes.md` 생성 로직과 로컬 웹뷰어(FastAPI)는 더미 세션 데이터로 렌더링까지
직접 확인했습니다.

## 알려진 제한 사항

- 화면 변경 감지는 perceptual hash 기반이라, 애니메이션이 있는 슬라이드나 마우스
  커서 움직임에도 민감할 수 있습니다. `--phash-threshold`로 조절하세요.
- Whisper 전사 품질은 마이크/루프백 음질과 모델 크기에 크게 좌우됩니다. 정확도가
  중요하면 `--whisper-model medium` 이상을 권장합니다.
- Claude 정리 단계는 섹션마다 API 호출 1회가 발생합니다(스크린샷 포함). 강의가 길고
  화면 전환이 잦으면 호출 수와 비용이 늘어날 수 있습니다.
