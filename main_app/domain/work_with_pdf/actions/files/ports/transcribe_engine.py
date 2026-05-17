from pathlib import Path
from typing import Protocol

from main_app.domain.work_with_pdf.actions.files.models import TranscribeConfig


class TranscribeEngine(Protocol):
    """
    Порт для движка транскрибации.

    Domain знает только про контракт "получить текст из WAV",
    но не знает про faster-whisper, WhisperModel, GPU/CPU и т.д.
    """

    def transcribe(self, wav_path: Path, cfg: TranscribeConfig) -> tuple[str, str | None]: ...
