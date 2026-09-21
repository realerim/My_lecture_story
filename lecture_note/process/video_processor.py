"""Zoom 클라우드/로컬 녹화 파일(mp4 등)을 사후 처리해 실시간 모드와 동일한
screen_events.jsonl / transcript.jsonl 구조를 만든다. ffmpeg가 PATH에 있어야 한다.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from lecture_note.config import Config
from lecture_note.notes import summarizer
from lecture_note.notes.builder import build_sections
from lecture_note.notes.markdown_writer import render_markdown
from lecture_note.session import Session, new_session_id
from lecture_note.transcribe.whisper_transcriber import Transcriber

logger = logging.getLogger(__name__)

_PTS_TIME_RE = re.compile(r"pts_time:([0-9.]+)")


def _check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg를 찾을 수 없습니다. 녹화본 처리에는 ffmpeg가 필요합니다. "
            "(macOS: brew install ffmpeg / Ubuntu: apt install ffmpeg / Windows: winget install ffmpeg)"
        )


def _run_ffmpeg(args: list[str]) -> str:
    _check_ffmpeg()
    result = subprocess.run(["ffmpeg", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 실행 실패:\n{result.stderr[-4000:]}")
    return result.stderr


def extract_audio(video_path: Path, out_wav_path: Path, samplerate: int = 16000) -> None:
    out_wav_path.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg(
        ["-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", str(samplerate), str(out_wav_path)]
    )


def extract_scene_frames(video_path: Path, out_dir: Path, threshold: float) -> list[float]:
    """화면이 바뀌는 시점마다 프레임을 out_dir/scene_%05d.png 로 저장하고, 각 프레임의
    타임스탬프(초) 리스트를 반환. 항상 t=0 프레임도 별도로 포함시킨다."""
    out_dir.mkdir(parents=True, exist_ok=True)

    stderr = _run_ffmpeg(
        [
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-vsync",
            "vfr",
            str(out_dir / "scene_%05d.png"),
        ]
    )
    timestamps = [float(m) for m in _PTS_TIME_RE.findall(stderr)]

    saved_frames = sorted(out_dir.glob("scene_*.png"))
    if len(saved_frames) != len(timestamps):
        logger.warning(
            "장면 프레임 수(%d)와 파싱된 타임스탬프 수(%d)가 다릅니다. 가능한 만큼만 사용합니다.",
            len(saved_frames),
            len(timestamps),
        )
        n = min(len(saved_frames), len(timestamps))
        saved_frames, timestamps = saved_frames[:n], timestamps[:n]

    # t=0 프레임 별도 추출 (scene 필터는 첫 프레임을 보통 선택하지 않음)
    first_frame = out_dir / "scene_00000.png"
    _run_ffmpeg(["-y", "-i", str(video_path), "-frames:v", "1", str(first_frame)])

    frames = [(0.0, first_frame)] + list(zip(timestamps, saved_frames))
    # 0초 근처 중복 제거
    deduped: list[tuple[float, Path]] = []
    for ts, path in sorted(frames, key=lambda x: x[0]):
        if deduped and ts - deduped[-1][0] < 0.5:
            continue
        deduped.append((ts, path))

    return deduped  # type: ignore[return-value]


def process_video(
    video_path: Path, config: Config, title: str | None = None, material_pdfs: list[Path] | None = None
) -> Session:
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    session = Session(new_session_id(title or video_path.stem))
    session.ensure_dirs()
    session.write_meta(title=title or video_path.stem, source_video=str(video_path), mode="process")

    if material_pdfs:
        from lecture_note.notes.materials import import_materials

        logger.info("강의 자료 %d개 불러오는 중...", len(material_pdfs))
        import_materials(session, material_pdfs)

    logger.info("오디오 추출 중...")
    audio_path = session.audio_chunks_dir / "full_audio.wav"
    extract_audio(video_path, audio_path, samplerate=config.audio_samplerate)

    logger.info("화면 전환 지점 추출 중...")
    tmp_frames_dir = session.root / "_tmp_frames"
    frames = extract_scene_frames(video_path, tmp_frames_dir, config.scene_change_threshold)

    for i, (ts, frame_path) in enumerate(frames, start=1):
        filename = f"frame_{i:05d}.png"
        dest = session.screenshots_dir / filename
        session.screenshots_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(frame_path), dest)
        session.append_screen_event(ts=round(ts, 2), image_rel_path=f"screenshots/{filename}", phash="")
    shutil.rmtree(tmp_frames_dir, ignore_errors=True)

    logger.info("음성 전사 중 (모델: %s)...", config.whisper_model)
    transcriber = Transcriber(config.whisper_model, config.whisper_device, config.whisper_compute_type, config.language)
    segments = transcriber.transcribe_file(audio_path, offset_seconds=0.0)
    for seg in segments:
        session.append_transcript_segment(seg["start"], seg["end"], seg["text"])

    finalize_notes(session, config, title or video_path.stem)
    return session


def finalize_notes(session: Session, config: Config, title: str) -> None:
    """저장된 screen_events/transcript로부터 섹션을 만들고, 필요하면 Claude로 정리한 뒤
    notes.md를 작성한다. 실시간 모드(record) 종료 시에도 이 함수를 재사용한다."""
    sections = build_sections(session.read_screen_events(), session.read_transcript_segments())

    api_key = os.environ.get("ANTHROPIC_API_KEY") if config.use_claude_summary else None
    if api_key:
        logger.info("Claude로 섹션 정리 중 (%d개 섹션)...", len(sections))
        materials = session.read_materials()
        summarizer.organize_sections(sections, session.root, api_key, config.claude_model, materials=materials)
        session.write_organized({s.index: s.organized_text for s in sections if s.organized_text})

    markdown = render_markdown(title, session.session_id, sections)
    session.notes_path.write_text(markdown, encoding="utf-8")
    logger.info("노트 작성 완료: %s", session.notes_path)
