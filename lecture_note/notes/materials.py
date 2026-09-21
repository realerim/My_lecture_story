"""수업 전에 미리 가진 강의 자료(PDF)를 페이지 단위로 불러와, 캡처된 화면 스크린샷과
가장 비슷한 페이지를 찾아준다. Claude가 그 페이지 내용을 함께 참고해 설명을 보강한다.

PPT(.pptx) 등은 PDF로 내보낸 뒤 사용하세요 (대부분의 프로그램에서 "PDF로 저장"을 지원).
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image
import imagehash

from lecture_note.session import Session

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 14
"""이 값보다 해시 거리가 크면 '같은 자료 페이지가 아니다'로 판단해 참고자료를 붙이지 않는다."""


def import_materials(session: Session, pdf_paths: list[Path]) -> list[dict]:
    """PDF들을 페이지별 PNG + 텍스트로 풀어 session.materials_dir에 저장.

    이미 렌더링된 자료가 있다면 덧붙인다. 여러 PDF를 줄 수 있다 (예: 교재 + 슬라이드).
    """
    import pymupdf

    session.materials_dir.mkdir(parents=True, exist_ok=True)
    pages = session.read_materials()
    next_index = len(pages)

    for pdf_path in pdf_paths:
        pdf_path = Path(pdf_path)
        doc = pymupdf.open(pdf_path)
        page_count = len(doc)
        for page_number in range(page_count):
            page = doc[page_number]
            pix = page.get_pixmap(dpi=110)
            filename = f"page_{next_index:04d}.png"
            image_path = session.materials_dir / filename
            pix.save(image_path)
            phash = str(imagehash.phash(Image.open(image_path)))
            text = page.get_text().strip()
            pages.append(
                {
                    "index": next_index,
                    "source": pdf_path.name,
                    "page_number": page_number + 1,
                    "image": f"materials/{filename}",
                    "phash": phash,
                    "text": text,
                }
            )
            next_index += 1
        doc.close()
        logger.info("강의 자료 '%s' %d페이지 추가", pdf_path.name, page_count)

    session.write_materials(pages)
    return pages


def find_best_match(screenshot_path: Path, pages: list[dict]) -> dict | None:
    """screenshot_path와 가장 비슷한 자료 페이지를 찾는다. 충분히 비슷한 게 없으면 None."""
    if not pages or not screenshot_path.exists():
        return None

    target_hash = imagehash.phash(Image.open(screenshot_path))
    best_page, best_distance = None, None
    for page in pages:
        distance = target_hash - imagehash.hex_to_hash(page["phash"])
        if best_distance is None or distance < best_distance:
            best_page, best_distance = page, distance

    if best_page is not None and best_distance <= MATCH_THRESHOLD:
        return best_page
    return None
