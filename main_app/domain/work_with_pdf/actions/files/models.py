from pathlib import Path
from typing import Literal

from pdfnik_contracts.txt_content import YouTubeMetadata
from pydantic import BaseModel, Field

__all__ = [
    "PreparedTarget",
    "RunMetrics",
    "RunResult",
    "TranscribeConfig",
    "YouTubeMetadata",
]


class PreparedTarget(BaseModel):
    target: str
    target_id: str
    base_name: str
    wav_path: Path
    audio_duration_sec: float | None = None
    youtube_metadata: YouTubeMetadata | None = None  # filled out only for URL sources


class TranscribeConfig(BaseModel):
    model: str
    device: str
    compute_type: str | None = None
    threads: int = Field(ge=1)
    workers: int = Field(ge=1)
    beam_size: int = Field(ge=1)
    patience: float = Field(ge=0.0)
    vad: bool = False
    lang: str = "auto"


class RunMetrics(BaseModel):
    wall_time_sec: float
    audio_duration_sec: float | None = None
    rtf: float | None = None


class RunResult(BaseModel):
    run_key: str
    target_id: str
    output_txt: Path
    detected_language: str | None = None
    metrics: RunMetrics
    cached: bool = False
    youtube_metadata: YouTubeMetadata | None = None  # Passed through from PreparedTarget

    status: Literal["ok", "failed"] = "ok"
    error: str | None = None
