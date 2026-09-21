"""사용자가 조정할 수 있는 캡처/전사/정리 설정."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    # 화면 감시
    screenshot_interval_sec: float = 2.0
    """화면을 몇 초 간격으로 확인할지."""
    phash_threshold: int = 6
    """perceptual hash 거리가 이 값을 넘으면 '화면이 바뀌었다'고 판단."""
    monitor_index: int = 1
    """mss 기준 모니터 번호 (1 = 주 모니터). 특정 창이 아니라 모니터 전체를 캡처."""

    # 오디오
    audio_device: str | int | None = None
    """sounddevice 장치 이름(부분일치) 또는 인덱스. None이면 시스템 기본 입력 장치."""
    audio_samplerate: int = 16000
    audio_channels: int = 1
    audio_chunk_seconds: float = 20.0
    """이 길이만큼 녹음될 때마다 하나의 청크로 잘라 전사기에 넘김."""

    # 전사
    whisper_model: str = "small"
    """faster-whisper 모델 크기: tiny/base/small/medium/large-v3 등."""
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    language: str = "ko"

    # 정리(요약)
    use_claude_summary: bool = True
    """ANTHROPIC_API_KEY가 있으면 Claude로 섹션별 내용을 정리. 없으면 원본 전사만 사용."""
    claude_model: str = "claude-sonnet-5"

    # 후처리(녹화본) 전용
    scene_change_threshold: float = 0.01
    """ffmpeg select='gt(scene,X)' 임계값. 낮을수록 더 자주 프레임을 잡음.

    흔히 예시로 보이는 0.3~0.4는 카메라 촬영 영상(피사체 움직임이 큰) 기준이라, 정지된
    발표 자료 화면 전환에는 지나치게 둔감하다. 실제로 3개 슬라이드짜리 정적인 화면
    녹화본으로 측정해보면 슬라이드 전환 시점의 scene 점수가 0.01~0.08 수준, 전환이
    없을 때는 0.0005 이하였다. 이 값(0.01)은 그 측정을 바탕으로 잡은 기본값이다."""
