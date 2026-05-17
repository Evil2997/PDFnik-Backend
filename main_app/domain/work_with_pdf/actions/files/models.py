from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class YouTubeMetadata(BaseModel):
    """
    YouTube video metadata obtained via yt-dlp --dump-json.
    All fields are optional: yt-dlp may return incomplete JSON
    (private videos, live streams, regional locks).
    """

    url: str
    title: str | None = None
    channel: str | None = None
    uploader: str | None = None  # Channel or uploader name
    upload_date: str | None = None  # "YYYYMMDD"
    duration_sec: float | None = None
    view_count: int | None = None
    description: str | None = None
    thumbnail_url: str | None = None

    @property
    def duration_str(self) -> str:
        """Human-readable duration: '1:23:45' or '3:21'."""
        if not self.duration_sec:
            return "неизвестно"
        total = int(self.duration_sec)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    @property
    def upload_date_str(self) -> str:
        """'20240315' → '15.03.2024'."""
        d = self.upload_date
        if not d or len(d) != 8:
            return ""
        return f"{d[6:8]}.{d[4:6]}.{d[:4]}"


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
