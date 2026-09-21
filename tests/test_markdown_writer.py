from lecture_note.notes.builder import Section
from lecture_note.notes.markdown_writer import fmt_ts, render_markdown


def test_fmt_ts_minutes_seconds():
    assert fmt_ts(0) == "00:00"
    assert fmt_ts(65) == "01:05"


def test_fmt_ts_hours_when_over_an_hour():
    assert fmt_ts(3725) == "01:02:05"


def test_render_markdown_empty_sections():
    md = render_markdown("제목", "sess1", [])
    assert "제목" in md
    assert "아직 기록된 내용이 없습니다" in md


def test_render_markdown_includes_image_and_text():
    sections = [Section(index=0, start=0, end=30, image="screenshots/frame_1.png", raw_text="hello world")]
    md = render_markdown("강의", "sess1", sections)
    assert "![슬라이드 1](screenshots/frame_1.png)" in md
    assert "hello world" in md
    assert "00:00 ~ 00:30" in md


def test_render_markdown_shows_organized_text_and_keeps_raw_in_details():
    sections = [
        Section(index=0, start=0, end=None, image=None, raw_text="raw transcript", organized_text="정리된 내용")
    ]
    md = render_markdown("강의", "sess1", sections)
    assert "정리된 내용" in md
    assert "<details><summary>원문 전사</summary>" in md
    assert "raw transcript" in md


def test_render_markdown_no_organized_text_skips_details_block():
    sections = [Section(index=0, start=0, end=None, image=None, raw_text="raw only")]
    md = render_markdown("강의", "sess1", sections)
    assert "raw only" in md
    assert "<details>" not in md
