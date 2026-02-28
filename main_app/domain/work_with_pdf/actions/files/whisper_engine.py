import logging
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

from voice_to_text__app.domain.models import TranscribeConfig

logger = logging.getLogger(__name__)


class WhisperEngine:
    """
    Управляет lifecycle WhisperModel.
    Гарантирует:
    - модель создаётся 1 раз
    - может переиспользоваться
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model: Optional[WhisperModel] = None
        self._device: Optional[str] = None
        self._compute_type: Optional[str] = None

    def load(self, cfg: TranscribeConfig) -> None:
        compute = cfg.compute_type or (
            "float16" if cfg.device.lower() == "cuda" else "int8"
        )

        if (
                self._model
                and self._device == cfg.device
                and self._compute_type == compute
        ):
            return

        logger.info(
            "Load WhisperModel | model=%s | device=%s | compute=%s",
            self.model_name,
            cfg.device,
            compute,
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

    def transcribe(
            self,
            wav_path: Path,
            cfg: TranscribeConfig,
    ) -> tuple[str, Optional[str]]:
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
