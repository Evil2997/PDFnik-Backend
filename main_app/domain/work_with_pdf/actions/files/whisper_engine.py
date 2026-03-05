import logging
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

from main_app.core.settings import settings
from main_app.domain.work_with_pdf.actions.files.models import TranscribeConfig

logger = logging.getLogger(__name__)


class WhisperEngine:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.TRANSCRIBE_MODEL
        self._model: Optional[WhisperModel] = None
        self._device: Optional[str] = None
        self._compute_type: Optional[str] = None
        self._threads: Optional[int] = None
        self._workers: Optional[int] = None

    def load(self, cfg: TranscribeConfig) -> None:
        compute = cfg.compute_type or (
            "float16" if cfg.device.lower() == "cuda" else "int8"
        )

        if (
            self._model
            and self._device == cfg.device
            and self._compute_type == compute
            and self._threads == cfg.threads
            and self._workers == cfg.workers
        ):
            return

        logger.info(
            "Load WhisperModel | model=%s | device=%s | compute=%s | thr=%s | wrk=%s",
            self.model_name,
            cfg.device,
            compute,
            cfg.threads,
            cfg.workers,
        )

        self._model = WhisperModel(
            self.model_name,
            device=cfg.device,
            compute_type=compute,
            cpu_threads=cfg.threads,
            num_workers=cfg.workers,
        )

        self._device = cfg.device
        self._compute_type = compute
        self._threads = cfg.threads
        self._workers = cfg.workers

    def transcribe(self, wav_path: Path, cfg: TranscribeConfig) -> tuple[str, Optional[str]]:
        if not self._model:
            self.load(cfg)

        segments, info = self._model.transcribe(
            str(wav_path),
            beam_size=cfg.beam_size,
            patience=cfg.patience,
            vad_filter=cfg.vad,
            language=None if cfg.lang == "auto" else cfg.lang,
        )

        text = "".join(seg.text for seg in segments).strip()
        detected = getattr(info, "language", None)

        return text, detected
