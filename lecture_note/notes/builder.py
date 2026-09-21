"""화면 변경 이벤트 타임라인 + 전사 구간을 하나의 '노트 섹션' 목록으로 병합.

이 모듈은 외부 라이브러리에 의존하지 않는 순수 로직이라 유닛 테스트로 검증하기 쉽다.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field


@dataclass
class Section:
    index: int
    start: float
    end: float | None  # None이면 세션 끝까지
    image: str | None  # 세션 루트 기준 상대 경로
    raw_text: str = ""
    organized_text: str | None = field(default=None)


def build_sections(screen_events: list[dict], transcript_segments: list[dict]) -> list[Section]:
    """screen_events: [{"ts","image",...}], transcript_segments: [{"start","end","text"}]."""
    events = sorted(screen_events, key=lambda e: e["ts"])
    segments = sorted(transcript_segments, key=lambda s: s["start"])

    if not events:
        if not segments:
            return []
        # 화면 캡처가 하나도 없으면 전체 전사를 한 섹션에 담는다.
        text = " ".join(s["text"] for s in segments).strip()
        return [Section(index=0, start=segments[0]["start"], end=None, image=None, raw_text=text)]

    starts = [e["ts"] for e in events]
    sections = [
        Section(
            index=i,
            start=e["ts"],
            end=events[i + 1]["ts"] if i + 1 < len(events) else None,
            image=e["image"],
        )
        for i, e in enumerate(events)
    ]

    texts: list[list[str]] = [[] for _ in sections]
    for seg in segments:
        # seg가 속하는 섹션: start <= seg.start 인 마지막 섹션. 첫 섹션 이전이면 첫 섹션에 흡수.
        pos = bisect_right(starts, seg["start"]) - 1
        pos = max(pos, 0)
        texts[pos].append(seg["text"])

    for section, chunks in zip(sections, texts):
        section.raw_text = " ".join(chunks).strip()

    return sections
