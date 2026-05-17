from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


class YouTubeMetadata(BaseModel):
    """
    Метаданные YouTube-видео, полученные через yt-dlp --dump-json.
    Все поля опциональны: yt-dlp может вернуть неполный JSON
    (приватные видео, живые трансляции, regional lock).
    """
    url: str
    title: Optional[str] = None
    channel: Optional[str] = None
    uploader: Optional[str] = None  # канал или имя загрузчика
    upload_date: Optional[str] = None  # "YYYYMMDD"
    duration_sec: Optional[float] = None  # в секундах
    view_count: Optional[int] = None
    description: Optional[str] = None  # первые 500 символов
    thumbnail_url: Optional[str] = None

    @property
    def duration_str(self) -> str:
        """Человекочитаемая длительность: '1:23:45' или '3:21'."""
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
    audio_duration_sec: Optional[float] = None
    youtube_metadata: Optional[YouTubeMetadata] = None  # заполняется только для URL-источников


class TranscribeConfig(BaseModel):
    model: str
    device: str
    compute_type: Optional[str] = None
    threads: int = Field(ge=1)
    workers: int = Field(ge=1)
    beam_size: int = Field(ge=1)
    patience: float = Field(ge=0.0)
    vad: bool = False
    lang: str = "auto"


class RunMetrics(BaseModel):
    wall_time_sec: float
    audio_duration_sec: Optional[float] = None
    rtf: Optional[float] = None


class RunResult(BaseModel):
    run_key: str
    target_id: str
    output_txt: Path
    detected_language: Optional[str] = None
    metrics: RunMetrics
    cached: bool = False
    youtube_metadata: Optional[YouTubeMetadata] = None  # прокидывается из PreparedTarget

    status: Literal["ok", "failed"] = "ok"
    error: Optional[str] = None
