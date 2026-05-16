import logging
import threading
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

from main_app.core.settings import settings
from main_app.domain.work_with_pdf.actions.files.models import TranscribeConfig

logger = logging.getLogger(__name__)


class WhisperEngine:
    """
    Thread-safe обёртка над faster-whisper.

    Проблема: WhisperEngine — синглтон, shared между несколькими asyncio-задачами,
    которые выполняются в ThreadPoolExecutor (run_in_executor).
    Без блокировки два потока с разными cfg могут одновременно перезагружать модель,
    приводя к race condition на self._model, self._device и т.д.

    Решение: Lock на всю операцию transcribe().
    Это сериализует транскрибирование, что правильно — Whisper и так CPU-bound
    и уже использует внутренний threadpool; параллельные запуски не дадут прироста.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.TRANSCRIBE_MODEL
        self._model: Optional[WhisperModel] = None
        self._device: Optional[str] = None
        self._compute_type: Optional[str] = None
        self._threads: Optional[int] = None
        self._workers: Optional[int] = None
        self._lock = threading.Lock()

    def load(self, cfg: TranscribeConfig) -> None:
        """
        Загружает (или перезагружает) модель.
        ВНИМАНИЕ: вызывается только из-под self._lock.
        """
        compute = cfg.compute_type or (
            "float16" if cfg.device.lower() == "cuda" else "int8"
        )

        already_loaded = (
                self._model is not None
                and self._device == cfg.device
                and self._compute_type == compute
                and self._threads == cfg.threads
                and self._workers == cfg.workers
        )
        if already_loaded:
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
        """
        Транскрибирует WAV-файл. Полностью сериализован через Lock:
        включая загрузку модели и генерацию сегментов (сегменты — lazy iterator,
        их нужно материализовать до выхода из-под блокировки).
        """
        with self._lock:
            self.load(cfg)

            segments, info = self._model.transcribe(
                str(wav_path),
                beam_size=cfg.beam_size,
                patience=cfg.patience,
                vad_filter=cfg.vad,
                language=None if cfg.lang == "auto" else cfg.lang,
            )

            # Материализуем lazy-iterator внутри lock.
            # Если вынести за пределы, другой поток может перезагрузить модель
            # пока мы ещё читаем сегменты старой.
            text = "".join(seg.text for seg in segments).strip()
            detected = getattr(info, "language", None)

        return text, detected
