"""Claude를 이용해 섹션별 원문 전사 + 화면 캡처를 교수님 강의 흐름에 맞게 정리.

ANTHROPIC_API_KEY가 없거나 use_claude_summary=False면 원문 전사를 그대로 사용한다
(builder.Section.raw_text가 이미 채워져 있으므로 별도 처리 없이 markdown_writer가
raw_text를 그대로 노출).
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from lecture_note.notes.builder import Section

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "당신은 대학 강의를 듣고 있는 학생을 돕는 노트 정리 도우미입니다. "
    "주어지는 것은 (1) 강의 중 화면에 띄워진 슬라이드/자료의 캡처 이미지와 "
    "(2) 그 화면이 떠 있던 구간 동안 교수님이 말한 내용의 음성 전사입니다. "
    "다음 규칙에 따라 한국어로 정리하세요:\n"
    "1. 화면에 보이는 핵심 텍스트/수식/그림을 간단히 언급하며 설명에 녹여내세요.\n"
    "2. 교수님의 설명 흐름(정의 -> 예시 -> 강조점 순 등)을 살려 불릿포인트로 정리하세요.\n"
    "3. 전사에 잡음이나 구어체 반복이 있으면 정제하되, 내용을 지어내지 마세요.\n"
    "4. 결과는 마크다운 불릿(-)만 사용하고, 제목(#)이나 서두 인사말은 넣지 마세요."
)


def _encode_image(path: Path) -> tuple[str, str]:
    media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return media_type, data


def organize_section(
    section: Section,
    session_root: Path,
    api_key: str,
    model: str,
    client=None,
) -> str:
    """섹션 하나를 Claude로 정리해 텍스트를 반환. 실패 시 원문 전사를 그대로 반환."""
    if not section.raw_text and not section.image:
        return section.raw_text

    try:
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)

        content: list[dict] = []
        if section.image:
            image_path = session_root / section.image
            if image_path.exists():
                media_type, data = _encode_image(image_path)
                content.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": data},
                    }
                )

        transcript_text = section.raw_text or "(이 구간의 음성 전사가 없습니다. 화면 내용만 보고 정리하세요.)"
        content.append({"type": "text", "text": f"[음성 전사]\n{transcript_text}"})

        response = client.messages.create(
            model=model,
            max_tokens=700,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        organized = "\n".join(parts).strip()
        return organized or section.raw_text
    except Exception:
        logger.exception("섹션 %s 정리 중 오류, 원문 전사로 대체합니다", section.index)
        return section.raw_text


def organize_sections(
    sections: list[Section],
    session_root: Path,
    api_key: str | None,
    model: str,
) -> None:
    """sections를 제자리에서 갱신 (section.organized_text 채움). api_key 없으면 아무것도 하지 않음."""
    if not api_key:
        logger.info("ANTHROPIC_API_KEY 없음: 원문 전사를 그대로 사용합니다.")
        return

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    for section in sections:
        section.organized_text = organize_section(section, session_root, api_key, model, client=client)
