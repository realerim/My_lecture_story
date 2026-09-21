"""화면(공유 화면 포함 모니터 전체)을 주기적으로 캡처하고, 내용이 바뀌었을 때만 저장한다.

Zoom API 연동이 아니라, 사용자가 Zoom 미팅에 참여해 둔 상태에서 이 프로세스가
백그라운드로 모니터 화면을 계속 지켜보는 방식이다. 따라서 Zoom뿐 아니라 화면에
띄워진 어떤 발표 자료든 동일하게 동작한다.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from PIL import Image
import imagehash

from lecture_note.session import Session

logger = logging.getLogger(__name__)


def compute_phash(image: Image.Image) -> imagehash.ImageHash:
    return imagehash.phash(image)


def is_changed(prev_hash: imagehash.ImageHash | None, new_hash: imagehash.ImageHash, threshold: int) -> bool:
    """이전 해시가 없으면(첫 프레임) 항상 변경으로 취급. 그 외엔 해밍 거리로 판단."""
    if prev_hash is None:
        return True
    return bool((new_hash - prev_hash) > threshold)


class ScreenWatcher:
    """별도 스레드에서 monitor_index 화면을 주기적으로 캡처하는 감시자."""

    def __init__(self, session: Session, interval_sec: float, phash_threshold: int, monitor_index: int = 1):
        self.session = session
        self.interval_sec = interval_sec
        self.phash_threshold = phash_threshold
        self.monitor_index = monitor_index
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_time: float | None = None
        self._frame_count = 0

    def start(self, start_time: float) -> None:
        self._start_time = start_time
        self.session.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, daemon=True, name="screen-watcher")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_sec + 5)

    def _run(self) -> None:
        # mss는 만든 스레드 안에서만 사용해야 하므로 스레드 진입 후 import/생성.
        import mss

        prev_hash: imagehash.ImageHash | None = None
        with mss.mss() as sct:
            monitors = sct.monitors
            if self.monitor_index >= len(monitors):
                logger.warning("monitor_index %s 없음, 0번(전체) 사용", self.monitor_index)
                monitor = monitors[0]
            else:
                monitor = monitors[self.monitor_index]

            while not self._stop_event.is_set():
                loop_start = time.monotonic()
                try:
                    raw = sct.grab(monitor)
                    image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                    new_hash = compute_phash(image)
                    if is_changed(prev_hash, new_hash, self.phash_threshold):
                        self._save_frame(image, new_hash)
                        prev_hash = new_hash
                except Exception:
                    logger.exception("화면 캡처 중 오류")

                elapsed = time.monotonic() - loop_start
                self._stop_event.wait(max(0.0, self.interval_sec - elapsed))

    def _save_frame(self, image: Image.Image, phash: imagehash.ImageHash) -> None:
        assert self._start_time is not None
        ts = time.time() - self._start_time
        self._frame_count += 1
        filename = f"frame_{self._frame_count:05d}.png"
        rel_path = f"screenshots/{filename}"
        image.save(self.session.screenshots_dir / filename)
        self.session.append_screen_event(ts=round(ts, 2), image_rel_path=rel_path, phash=str(phash))
        logger.info("화면 변경 감지 (t=%.1fs) -> %s", ts, rel_path)
