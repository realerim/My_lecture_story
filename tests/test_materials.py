from pathlib import Path

import pymupdf

import lecture_note.session as session_mod
from lecture_note.notes.materials import find_best_match, import_materials
from lecture_note.session import Session


def _make_pdf(path: Path, texts: list[str]) -> None:
    doc = pymupdf.open()
    for text in texts:
        page = doc.new_page()
        page.insert_text((50, 100), text, fontsize=24)
    doc.save(path)
    doc.close()


def test_import_materials_renders_pages_with_text(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "DATA_ROOT", tmp_path)
    pdf_path = tmp_path / "slides.pdf"
    _make_pdf(pdf_path, ["Chapter 1: Introduction", "Chapter 2: Normalization"])

    session = Session("s1")
    pages = import_materials(session, [pdf_path])

    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert "Chapter 1" in pages[0]["text"]
    assert pages[1]["page_number"] == 2
    assert "Chapter 2" in pages[1]["text"]
    assert (session.materials_dir / "page_0000.png").exists()
    assert (session.materials_dir / "page_0001.png").exists()
    # 다시 읽어도 저장된 내용이 그대로 남아 있어야 함
    assert session.read_materials() == pages


def test_import_materials_appends_across_multiple_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "DATA_ROOT", tmp_path)
    pdf1 = tmp_path / "a.pdf"
    pdf2 = tmp_path / "b.pdf"
    _make_pdf(pdf1, ["Only page of A"])
    _make_pdf(pdf2, ["Only page of B"])

    session = Session("s2")
    import_materials(session, [pdf1])
    pages = import_materials(session, [pdf2])

    assert len(pages) == 2
    assert pages[0]["index"] == 0
    assert pages[1]["index"] == 1


def test_find_best_match_returns_identical_page(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "DATA_ROOT", tmp_path)
    pdf_path = tmp_path / "slides.pdf"
    _make_pdf(pdf_path, ["Only one distinctive page of content"])

    session = Session("s3")
    pages = import_materials(session, [pdf_path])

    # 방금 렌더링된 자료 페이지 이미지를 '화면 캡처'인 것처럼 그대로 넘겨본다 (완전 동일하므로 매칭돼야 함)
    screenshot_path = session.materials_dir / "page_0000.png"
    match = find_best_match(screenshot_path, pages)

    assert match is not None
    assert match["page_number"] == 1


def test_find_best_match_returns_none_when_no_materials(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "DATA_ROOT", tmp_path)
    session = Session("s4")
    session.ensure_dirs()
    fake_screenshot = session.screenshots_dir / "frame_00001.png"
    from PIL import Image

    Image.new("RGB", (10, 10)).save(fake_screenshot)

    assert find_best_match(fake_screenshot, []) is None


def test_find_best_match_returns_none_for_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "DATA_ROOT", tmp_path)
    assert find_best_match(tmp_path / "does-not-exist.png", [{"phash": "0" * 16}]) is None
