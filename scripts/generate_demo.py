#!/usr/bin/env python3
"""데모용 가짜 '강의 영상'을 만든다. 실제 Zoom 없이도 process 모드를 바로 테스트하기
위한 것으로, ffmpeg + espeak-ng로 화면이 바뀌는 3개 구간짜리 mp4와, 같은 내용의 PDF
슬라이드를 함께 생성한다.

요구사항: ffmpeg, espeak-ng (시스템 패키지), 한국어를 표시할 수 있는 폰트(Noto Sans CJK 등).

    python scripts/generate_demo.py [출력디렉터리(기본 demo/)]
    lecture-note process demo/lecture.mp4 --materials demo/slides.pdf --whisper-model tiny --no-claude
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SLIDES = [
    {
        "title": "1강: 관계형 데이터베이스 소개",
        "bg": "0x1e3a8a",
        "narration": (
            "안녕하세요. 오늘은 관계형 데이터베이스의 기본 개념에 대해 알아보겠습니다. "
            "데이터는 테이블 형태로 저장되고, 각 테이블은 행과 열로 구성됩니다."
        ),
    },
    {
        "title": "2강: 정규화란 무엇인가",
        "bg": "0x065f46",
        "narration": (
            "이번에는 정규화에 대해 설명하겠습니다. 정규화는 데이터 중복을 줄이고 "
            "무결성을 높이는 과정입니다. 제1정규형부터 제3정규형까지 순서대로 살펴봅니다."
        ),
    },
    {
        "title": "3강: 정규화 예제",
        "bg": "0x7c2d12",
        "narration": (
            "화면에 보이는 예시처럼, 학생 테이블과 수강 테이블을 분리하면 "
            "제3정규형을 만족시킬 수 있습니다. 이렇게 하면 성적이 바뀔 때마다 "
            "학생 정보를 중복해서 수정할 필요가 없어집니다."
        ),
    },
]


def _find_korean_font() -> str:
    for candidate in subprocess.run(["fc-list"], capture_output=True, text=True).stdout.splitlines():
        if "Noto Sans CJK KR" in candidate or "NanumGothic" in candidate:
            return candidate.split(":")[0]
    raise RuntimeError(
        "한국어 폰트를 찾지 못했습니다. 'apt install fonts-noto-cjk' 등으로 CJK 폰트를 설치하세요."
    )


def _check_tools() -> None:
    for tool in ("ffmpeg", "ffprobe", "espeak-ng"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"'{tool}'을(를) 찾을 수 없습니다. 먼저 설치하세요.")


def _duration_sec(wav_path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def _make_slide_clip(slide: dict, narration_wav: Path, font_path: str, out_path: Path) -> None:
    duration = max(_duration_sec(narration_wav) + 0.5, 3.0)
    title = slide["title"].replace(":", "\\:").replace("'", "’")
    drawtext = (
        f"drawtext=fontfile='{font_path}':text='{title}':fontsize=54:fontcolor=white:"
        f"x=(w-text_w)/2:y=(h-text_h)/2"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={slide['bg']}:s=1280x720:d={duration}",
            "-i",
            str(narration_wav),
            "-vf",
            drawtext,
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


def _concat_clips(clips: list[Path], out_path: Path, workdir: Path) -> None:
    list_file = workdir / "concat_list.txt"
    list_file.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)],
        check=True,
        capture_output=True,
    )


def _hex_to_rgb01(hex_color: str) -> tuple[float, float, float]:
    value = int(hex_color, 16)
    return ((value >> 16 & 255) / 255, (value >> 8 & 255) / 255, (value & 255) / 255)


def _make_slides_pdf(out_path: Path, font_path: str) -> None:
    """실제 발표자료처럼, 화면 공유되는 슬라이드와 같은 배경색/제목을 재현해 pHash 매칭이
    실제로 맞아떨어지는지 확인할 수 있게 만든다. 화면 캡처만으로는 부족한 세부 설명을
    아래쪽에 흰 텍스트로 추가로 담아, 강의자료 참고 기능이 의미 있게 동작하도록 한다."""
    import pymupdf

    doc = pymupdf.open()
    for slide in SLIDES:
        page = doc.new_page(width=1280, height=720)
        rgb = _hex_to_rgb01(slide["bg"])
        page.draw_rect(page.rect, color=None, fill=rgb)
        page.insert_font(fontname="kr", fontfile=font_path)

        title = slide["title"]
        title_width = pymupdf.Font(fontfile=font_path).text_length(title, fontsize=54)
        page.insert_text(
            ((1280 - title_width) / 2, 340), title, fontsize=54, color=(1, 1, 1), fontname="kr"
        )

        detail = slide["narration"]
        page.insert_textbox(
            pymupdf.Rect(80, 420, 1200, 680),
            detail,
            fontsize=16,
            color=(1, 1, 1),
            align=1,
            fontname="kr",
        )
    doc.save(out_path)
    doc.close()


def main() -> None:
    _check_tools()
    font_path = _find_korean_font()

    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("demo")
    out_dir.mkdir(parents=True, exist_ok=True)
    workdir = out_dir / "_build"
    workdir.mkdir(parents=True, exist_ok=True)

    clips = []
    for i, slide in enumerate(SLIDES, start=1):
        wav_path = workdir / f"narration_{i}.wav"
        subprocess.run(
            ["espeak-ng", "-v", "ko", "-s", "150", "-w", str(wav_path), slide["narration"]],
            check=True,
            capture_output=True,
        )
        clip_path = workdir / f"slide_{i}.mp4"
        print(f"[{i}/{len(SLIDES)}] '{slide['title']}' 구간 생성 중...")
        _make_slide_clip(slide, wav_path, font_path, clip_path)
        clips.append(clip_path)

    video_path = out_dir / "lecture.mp4"
    _concat_clips(clips, video_path, workdir)
    shutil.rmtree(workdir)

    pdf_path = out_dir / "slides.pdf"
    _make_slides_pdf(pdf_path, font_path)

    print(f"\n완료: {video_path}, {pdf_path}")
    print(
        "테스트:\n"
        f"  lecture-note process {video_path} --materials {pdf_path} "
        "--whisper-model tiny --no-claude\n"
        "  lecture-note serve"
    )


if __name__ == "__main__":
    main()
