"""세션(한 번의 강의 녹화/캡처)이 디스크에 어떤 구조로 저장되는지 정의.

data/sessions/<session_id>/
    meta.json            세션 메타데이터 (제목, 시작 시각, 설정)
    screenshots/          화면이 바뀔 때마다 저장되는 PNG
    audio_chunks/          오디오 청크 (전사 후 삭제해도 무방)
    screen_events.jsonl    {"ts": 12.3, "image": "screenshots/frame_000123.png", "phash": "..."}
    transcript.jsonl       {"start": 10.0, "end": 18.4, "text": "..."}
    materials/              미리 업로드한 강의 자료(PDF) 페이지 이미지 + materials.json
    notes.md               최종 마크다운 노트
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

DATA_ROOT = Path("data/sessions")


def new_session_id(title: str | None = None) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if title:
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in title).strip("-")
        return f"{stamp}_{safe}" if safe else stamp
    return stamp


@dataclass
class Session:
    session_id: str
    root: Path = field(init=False)

    def __post_init__(self) -> None:
        self.root = DATA_ROOT / self.session_id

    @property
    def screenshots_dir(self) -> Path:
        return self.root / "screenshots"

    @property
    def audio_chunks_dir(self) -> Path:
        return self.root / "audio_chunks"

    @property
    def screen_events_path(self) -> Path:
        return self.root / "screen_events.jsonl"

    @property
    def transcript_path(self) -> Path:
        return self.root / "transcript.jsonl"

    @property
    def meta_path(self) -> Path:
        return self.root / "meta.json"

    @property
    def notes_path(self) -> Path:
        return self.root / "notes.md"

    @property
    def organized_path(self) -> Path:
        return self.root / "organized.json"

    @property
    def materials_dir(self) -> Path:
        return self.root / "materials"

    @property
    def materials_path(self) -> Path:
        return self.materials_dir / "materials.json"

    def write_materials(self, pages: list[dict]) -> None:
        self.materials_dir.mkdir(parents=True, exist_ok=True)
        self.materials_path.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_materials(self) -> list[dict]:
        if not self.materials_path.exists():
            return []
        return json.loads(self.materials_path.read_text(encoding="utf-8"))

    def write_organized(self, organized_by_index: dict[int, str]) -> None:
        payload = {str(k): v for k, v in organized_by_index.items()}
        self.organized_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_organized(self) -> dict[int, str]:
        if not self.organized_path.exists():
            return {}
        raw = json.loads(self.organized_path.read_text(encoding="utf-8"))
        return {int(k): v for k, v in raw.items()}

    def ensure_dirs(self) -> None:
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.audio_chunks_dir.mkdir(parents=True, exist_ok=True)

    def write_meta(self, **fields) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {"session_id": self.session_id, **fields}
        self.meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_meta(self) -> dict:
        if not self.meta_path.exists():
            return {"session_id": self.session_id}
        return json.loads(self.meta_path.read_text(encoding="utf-8"))

    def append_jsonl(self, path: Path, record: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        records = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def append_screen_event(self, ts: float, image_rel_path: str, phash: str) -> None:
        self.append_jsonl(self.screen_events_path, {"ts": ts, "image": image_rel_path, "phash": phash})

    def append_transcript_segment(self, start: float, end: float, text: str) -> None:
        self.append_jsonl(self.transcript_path, {"start": start, "end": end, "text": text})

    def read_screen_events(self) -> list[dict]:
        return self.read_jsonl(self.screen_events_path)

    def read_transcript_segments(self) -> list[dict]:
        return self.read_jsonl(self.transcript_path)


def list_sessions() -> list[Session]:
    if not DATA_ROOT.exists():
        return []
    sessions = [Session(p.name) for p in sorted(DATA_ROOT.iterdir(), reverse=True) if p.is_dir()]
    return sessions
