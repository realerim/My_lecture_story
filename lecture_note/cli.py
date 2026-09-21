from __future__ import annotations

import argparse
import logging
import signal
import time
from pathlib import Path

from lecture_note.config import Config

logger = logging.getLogger("lecture_note")


def _build_config(args: argparse.Namespace) -> Config:
    cfg = Config()
    if getattr(args, "interval", None) is not None:
        cfg.screenshot_interval_sec = args.interval
    if getattr(args, "phash_threshold", None) is not None:
        cfg.phash_threshold = args.phash_threshold
    if getattr(args, "monitor", None) is not None:
        cfg.monitor_index = args.monitor
    if getattr(args, "audio_device", None) is not None:
        cfg.audio_device = args.audio_device
    if getattr(args, "whisper_model", None) is not None:
        cfg.whisper_model = args.whisper_model
    if getattr(args, "language", None) is not None:
        cfg.language = args.language
    if getattr(args, "scene_threshold", None) is not None:
        cfg.scene_change_threshold = args.scene_threshold
    if getattr(args, "no_claude", False):
        cfg.use_claude_summary = False
    return cfg


def cmd_record(args: argparse.Namespace) -> None:
    from lecture_note.capture.audio_recorder import AudioRecorder
    from lecture_note.capture.screen_watcher import ScreenWatcher
    from lecture_note.process.video_processor import finalize_notes
    from lecture_note.session import Session, new_session_id
    from lecture_note.transcribe.whisper_transcriber import LiveTranscriptionWorker, Transcriber

    cfg = _build_config(args)
    title = args.title or "강의"
    session = Session(new_session_id(title))
    session.ensure_dirs()
    session.write_meta(title=title, mode="record")

    if args.materials:
        from lecture_note.notes.materials import import_materials

        print(f"[lecture-note] 강의 자료 {len(args.materials)}개 불러오는 중...")
        import_materials(session, [Path(p) for p in args.materials])

    transcriber = Transcriber(cfg.whisper_model, cfg.whisper_device, cfg.whisper_compute_type, cfg.language)
    live_worker = LiveTranscriptionWorker(session, transcriber)

    audio_recorder = AudioRecorder(
        session,
        samplerate=cfg.audio_samplerate,
        channels=cfg.audio_channels,
        chunk_seconds=cfg.audio_chunk_seconds,
        device=cfg.audio_device,
        on_chunk_ready=live_worker.handle_chunk,
    )
    screen_watcher = ScreenWatcher(
        session,
        interval_sec=cfg.screenshot_interval_sec,
        phash_threshold=cfg.phash_threshold,
        monitor_index=cfg.monitor_index,
    )

    start_time = time.time()
    print(f"[lecture-note] 세션 시작: {session.session_id}")
    print(f"[lecture-note] 노트 폴더: {session.root}")
    print("[lecture-note] 다른 터미널에서 'lecture-note serve'를 실행하면 실시간으로 노트를 볼 수 있습니다.")
    print("[lecture-note] 중지하려면 Ctrl+C 를 누르세요.")

    screen_watcher.start(start_time)
    audio_recorder.start(start_time)

    stop = {"flag": False}

    def _handle_sigint(_sig, _frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handle_sigint)
    try:
        while not stop["flag"]:
            time.sleep(0.5)
    finally:
        print("\n[lecture-note] 중지 중... 캡처를 마무리하고 노트를 정리합니다.")
        screen_watcher.stop()
        audio_recorder.stop()
        finalize_notes(session, cfg, title)
        print(f"[lecture-note] 완료: {session.notes_path}")


def cmd_process(args: argparse.Namespace) -> None:
    from lecture_note.process.video_processor import process_video

    cfg = _build_config(args)
    material_pdfs = [Path(p) for p in args.materials] if args.materials else None
    session = process_video(Path(args.video), cfg, title=args.title, material_pdfs=material_pdfs)
    print(f"[lecture-note] 완료: {session.notes_path}")


def cmd_serve(args: argparse.Namespace) -> None:
    from lecture_note.web.app import run

    run(host=args.host, port=args.port)


def cmd_list_devices(_args: argparse.Namespace) -> None:
    from lecture_note.capture.audio_recorder import list_audio_devices

    for dev in list_audio_devices():
        print(f"[{dev['index']}] {dev['name']} (입력 채널 {dev['channels']})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lecture-note", description="Zoom 강의를 실시간/녹화본으로 정리하는 노트 도구")
    sub = parser.add_subparsers(dest="command", required=True)

    common_note = argparse.ArgumentParser(add_help=False)
    common_note.add_argument("--whisper-model", help="tiny/base/small/medium/large-v3 (기본 small)")
    common_note.add_argument("--language", help="전사 언어 코드 (기본 ko)")
    common_note.add_argument("--no-claude", action="store_true", help="Claude 정리 단계를 건너뛰고 원문 전사만 사용")
    common_note.add_argument(
        "--materials",
        nargs="+",
        metavar="PDF",
        help="미리 가진 강의 자료 PDF 경로(여러 개 가능). 화면과 비슷한 페이지를 찾아 설명에 참고합니다.",
    )

    p_record = sub.add_parser("record", parents=[common_note], help="Zoom 미팅에 참여한 상태에서 화면/음성을 실시간으로 감시")
    p_record.add_argument("--title", help="강의 제목")
    p_record.add_argument("--interval", type=float, help="화면 확인 간격(초), 기본 2.0")
    p_record.add_argument("--phash-threshold", type=int, help="화면 변경 감지 민감도(낮을수록 민감), 기본 6")
    p_record.add_argument("--monitor", type=int, help="캡처할 모니터 번호(1=주 모니터), 기본 1")
    p_record.add_argument("--audio-device", help="오디오 입력 장치 이름 일부 또는 인덱스 (list-devices로 확인)")
    p_record.set_defaults(func=cmd_record)

    p_process = sub.add_parser("process", parents=[common_note], help="이미 녹화된 Zoom 영상 파일을 처리")
    p_process.add_argument("video", help="녹화 영상 파일 경로 (mp4 등)")
    p_process.add_argument("--title", help="강의 제목")
    p_process.add_argument("--scene-threshold", type=float, help="화면 전환 감지 민감도(0~1, 낮을수록 민감), 기본 0.01")
    p_process.set_defaults(func=cmd_process)

    p_serve = sub.add_parser("serve", help="로컬 웹뷰어 실행")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    p_devices = sub.add_parser("list-devices", help="사용 가능한 오디오 입력 장치 목록")
    p_devices.set_defaults(func=cmd_list_devices)

    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
