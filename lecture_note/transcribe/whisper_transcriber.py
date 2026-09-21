"""faster-whisper를 이용한 로컬 음성 전사. 별도 API 키 없이 동작한다."""
from __future__ import annotations

import logging
from pathlib import Path

from lecture_note.session import Session

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, model_size: str, device: str, compute_type: str, language: str):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            logger.info("Whisper 모델 로딩 중 (%s, %s/%s)...", self.model_size, self.device, self.compute_type)
            self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model

    def transcribe_file(self, path: Path, offset_seconds: float = 0.0) -> list[dict]:
        """path의 오디오를 전사해 {"start","end","text"} 리스트로 반환.

        start/end는 offset_seconds를 더해 세션 시작 기준 절대 초 단위로 맞춘다.
        """
        model = self._get_model()
        segments, _info = model.transcribe(str(path), language=self.language, vad_filter=True)
        results = []
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue
            results.append(
                {
                    "start": round(seg.start + offset_seconds, 2),
                    "end": round(seg.end + offset_seconds, 2),
                    "text": text,
                }
            )
        return results


class LiveTranscriptionWorker:
    """AudioRecorder.on_chunk_ready 콜백으로 넘겨 쓰는 어댑터.

    청크 WAV가 완성될 때마다 곧바로 전사하고 세션의 transcript.jsonl에 append한다.
    """

    def __init__(self, session: Session, transcriber: Transcriber, delete_chunk_after: bool = True):
        self.session = session
        self.transcriber = transcriber
        self.delete_chunk_after = delete_chunk_after

    def handle_chunk(self, path: Path, start_ts: float, end_ts: float) -> None:
        try:
            segments = self.transcriber.transcribe_file(path, offset_seconds=start_ts)
        except Exception:
            logger.exception("청크 전사 실패: %s", path)
            return
        for seg in segments:
            self.session.append_transcript_segment(seg["start"], seg["end"], seg["text"])
        logger.info("청크 전사 완료 (t=%.1f~%.1fs, %d개 구간)", start_ts, end_ts, len(segments))
        if self.delete_chunk_after:
            try:
                path.unlink()
            except OSError:
                pass
