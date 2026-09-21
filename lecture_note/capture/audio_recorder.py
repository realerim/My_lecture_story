"""마이크 또는 루프백(시스템 사운드) 오디오를 청크 단위 WAV 파일로 녹음한다.

Zoom 참가자들의 목소리를 잡으려면 '시스템 출력을 그대로 입력으로 받는' 루프백
장치가 필요하다. OS별로 다음과 같이 준비한다.

- Windows: '스테레오 믹스(Stereo Mix)'를 녹음 장치로 활성화하거나 VB-Audio Cable 사용.
- macOS: 코어오디오는 기본적으로 루프백을 지원하지 않으므로 BlackHole(무료) 등
  가상 오디오 장치를 설치하고 멀티출력장치로 스피커+BlackHole을 묶어 사용.
- Linux(PulseAudio/Pipewire): 출력 장치의 'Monitor' 소스를 입력으로 선택.

준비한 장치 이름을 Config.audio_device 에 지정하면 된다 (list-devices 명령으로 확인).
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf

from lecture_note.session import Session

logger = logging.getLogger(__name__)

OnChunkReady = Callable[[Path, float, float], None]


def list_audio_devices() -> list[dict]:
    import sounddevice as sd

    devices = []
    for idx, info in enumerate(sd.query_devices()):
        if info.get("max_input_channels", 0) > 0:
            devices.append({"index": idx, "name": info["name"], "channels": info["max_input_channels"]})
    return devices


def resolve_device(device: str | int | None):
    if device is None or isinstance(device, int):
        return device
    import sounddevice as sd

    needle = device.lower()
    for idx, info in enumerate(sd.query_devices()):
        if needle in info["name"].lower() and info.get("max_input_channels", 0) > 0:
            return idx
    raise ValueError(f"'{device}' 이름을 포함하는 입력 장치를 찾지 못했습니다. list-devices로 확인하세요.")


class AudioRecorder:
    """chunk_seconds 길이만큼 모이면 WAV로 저장하고 on_chunk_ready 콜백을 호출."""

    def __init__(
        self,
        session: Session,
        samplerate: int,
        channels: int,
        chunk_seconds: float,
        device: str | int | None = None,
        on_chunk_ready: OnChunkReady | None = None,
    ):
        self.session = session
        self.samplerate = samplerate
        self.channels = channels
        self.chunk_seconds = chunk_seconds
        self.device = device
        self.on_chunk_ready = on_chunk_ready

        self._block_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stop_event = threading.Event()
        self._writer_thread: threading.Thread | None = None
        self._stream = None
        self._start_time: float | None = None
        self._chunk_index = 0

    def start(self, start_time: float) -> None:
        import sounddevice as sd

        self._start_time = start_time
        self.session.audio_chunks_dir.mkdir(parents=True, exist_ok=True)
        device_index = resolve_device(self.device)

        def callback(indata, frames, time_info, status):
            if status:
                logger.warning("오디오 상태 경고: %s", status)
            self._block_queue.put(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            device=device_index,
            callback=callback,
        )
        self._stream.start()
        self._writer_thread = threading.Thread(target=self._run_writer, daemon=True, name="audio-writer")
        self._writer_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
        if self._writer_thread is not None:
            self._writer_thread.join(timeout=self.chunk_seconds + 5)

    def _run_writer(self) -> None:
        assert self._start_time is not None
        target_frames = int(self.chunk_seconds * self.samplerate)
        buffer: list[np.ndarray] = []
        buffered_frames = 0
        chunk_start_ts = time.time() - self._start_time

        while not (self._stop_event.is_set() and self._block_queue.empty()):
            try:
                block = self._block_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            buffer.append(block)
            buffered_frames += len(block)
            if buffered_frames >= target_frames:
                chunk_end_ts = time.time() - self._start_time
                self._flush(buffer, chunk_start_ts, chunk_end_ts)
                buffer = []
                buffered_frames = 0
                chunk_start_ts = chunk_end_ts

        if buffer:
            chunk_end_ts = time.time() - self._start_time
            self._flush(buffer, chunk_start_ts, chunk_end_ts)

    def _flush(self, buffer: list[np.ndarray], start_ts: float, end_ts: float) -> None:
        data = np.concatenate(buffer, axis=0)
        self._chunk_index += 1
        filename = f"chunk_{self._chunk_index:05d}.wav"
        path = self.session.audio_chunks_dir / filename
        sf.write(path, data, self.samplerate)
        logger.info("오디오 청크 저장 (t=%.1f~%.1fs) -> %s", start_ts, end_ts, filename)
        if self.on_chunk_ready is not None:
            self.on_chunk_ready(path, start_ts, end_ts)
