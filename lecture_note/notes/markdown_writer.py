"""Section 목록을 사람이 읽기 좋은 마크다운 노트로 변환."""
from __future__ import annotations

from lecture_note.notes.builder import Section


def fmt_ts(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def render_markdown(title: str, session_id: str, sections: list[Section]) -> str:
    lines = [f"# {title}", "", f"_세션 ID: {session_id}_", ""]

    if not sections:
        lines.append("_아직 기록된 내용이 없습니다._")
        return "\n".join(lines)

    for section in sections:
        time_range = fmt_ts(section.start)
        if section.end is not None:
            time_range += f" ~ {fmt_ts(section.end)}"
        lines.append(f"## [{time_range}]")
        lines.append("")

        if section.image:
            lines.append(f"![슬라이드 {section.index + 1}]({section.image})")
            lines.append("")

        body = (section.organized_text or section.raw_text or "").strip()
        if body:
            lines.append(body)
        else:
            lines.append("_(이 구간에는 음성 내용이 없습니다)_")
        lines.append("")

        if section.organized_text and section.raw_text:
            lines.append("<details><summary>원문 전사</summary>")
            lines.append("")
            lines.append(section.raw_text)
            lines.append("")
            lines.append("</details>")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
