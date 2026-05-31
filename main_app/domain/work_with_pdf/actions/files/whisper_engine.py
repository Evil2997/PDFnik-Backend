import logging
import threading
from pathlib import Path

from faster_whisper import WhisperModel

from main_app.core.settings import settings
from main_app.domain.work_with_pdf.actions.files.models import TranscribeConfig

logger = logging.getLogger(__name__)


class WhisperEngine:
    """
    A thread-safe wrapper around faster-whisper.

    Problem: WhisperEngine is a singleton shared across multiple asyncio tasks
    executing within a ThreadPoolExecutor (via `run_in_executor`).
    Without locking, two threads with different configurations could attempt to reload the model simultaneously,
    leading to a race condition involving `self._model`, `self._device`, etc.

    Solution: Apply a Lock to the entire `transcribe()` operation.
    This serializes the transcription process, which is appropriate—Whisper is inherently CPU-bound
    and already utilizes an internal thread pool; running multiple instances in parallel would yield no performance gains.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.TRANSCRIBE_MODEL
        self._model: WhisperModel | None = None
        self._device: str | None = None
        self._compute_type: str | None = None
        self._threads: int | None = None
        self._workers: int | None = None
        self._lock = threading.Lock()

    def load(self, cfg: TranscribeConfig) -> None:
        """
        Loads (or reloads) the model.
        WARNING: Must be called only while holding self._lock.
        """
        compute = cfg.compute_type or ("float16" if cfg.device.lower() == "cuda" else "int8")

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

    def transcribe(self, wav_path: Path, cfg: TranscribeConfig) -> tuple[str, str | None]:
        """
        Transcribes a WAV file. Fully serialized via a Lock:
        including model loading and segment generation (segments are a lazy iterator
        and must be materialized before releasing the lock).
        """
        with self._lock:
            self.load(cfg)
            assert self._model is not None

            segments, info = self._model.transcribe(
                str(wav_path),
                beam_size=cfg.beam_size,
                patience=cfg.patience,
                vad_filter=cfg.vad,
                language=None if cfg.lang == "auto" else cfg.lang,
            )

            # Materialize the lazy iterator inside the lock.
            # If moved outside, another thread could reload the model
            # while we are still reading segments of the old one.
            text = "".join(seg.text for seg in segments).strip()
            detected = getattr(info, "language", None)

        return text, detected
