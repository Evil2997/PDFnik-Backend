from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PreparedTarget(BaseModel):
    target: str
    target_id: str
    base_name: str
    wav_path: Path
    audio_duration_sec: Optional[float] = None


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

    status: Literal["ok", "failed"] = "ok"
    error: Optional[str] = None
