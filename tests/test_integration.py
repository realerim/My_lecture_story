import os

import lecture_note.session as session_mod
from lecture_note.config import Config
from lecture_note.process.video_processor import finalize_notes
from lecture_note.session import Session


def test_finalize_notes_without_claude_key(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "DATA_ROOT", tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    session = Session("test-session")
    session.ensure_dirs()
    session.append_screen_event(ts=0, image_rel_path="screenshots/frame_1.png", phash="x")
    session.append_screen_event(ts=20, image_rel_path="screenshots/frame_2.png", phash="y")
    session.append_transcript_segment(1, 5, "첫 번째 슬라이드 설명입니다.")
    session.append_transcript_segment(21, 25, "두 번째 슬라이드 설명입니다.")

    cfg = Config(use_claude_summary=True)  # 키가 없으므로 자동으로 건너뛰어야 함
    finalize_notes(session, cfg, "테스트 강의")

    assert session.notes_path.exists()
    md = session.notes_path.read_text(encoding="utf-8")
    assert "테스트 강의" in md
    assert "첫 번째 슬라이드 설명입니다." in md
    assert "두 번째 슬라이드 설명입니다." in md
    assert "![슬라이드 1](screenshots/frame_1.png)" in md
    assert not session.organized_path.exists()


def test_finalize_notes_skips_claude_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "DATA_ROOT", tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-not-called")

    session = Session("test-session-2")
    session.ensure_dirs()
    session.append_screen_event(ts=0, image_rel_path="screenshots/frame_1.png", phash="x")
    session.append_transcript_segment(1, 5, "설명")

    cfg = Config(use_claude_summary=False)
    finalize_notes(session, cfg, "제목")

    assert session.notes_path.exists()
    assert not session.organized_path.exists()
