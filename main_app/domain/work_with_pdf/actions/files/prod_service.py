import logging
from pathlib import Path

from main_app.domain.work_with_pdf.actions.files.models import RunResult, TranscribeConfig
from main_app.domain.work_with_pdf.actions.files.ports.run_repository import RunRepository
from main_app.domain.work_with_pdf.actions.files.ports.target_preparer import TargetPreparer
from main_app.domain.work_with_pdf.actions.files.ports.transcribe_engine import TranscribeEngine
from main_app.domain.work_with_pdf.actions.files.run_logic import run_once

logger = logging.getLogger(__name__)


def transcribe(
    *,
    target: str,
    cfg: TranscribeConfig,
    out_dir: Path,
    repo: RunRepository,
    engine: TranscribeEngine,
    preparer: TargetPreparer,
) -> RunResult:
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    prepared = preparer.prepare(target, work_dir=out_dir)

    res = run_once(
        prepared=prepared,
        cfg=cfg,
        out_dir=out_dir,
        repo=repo,
        engine=engine,
        allow_skip=True,
    )

    # FIX: раньше logger.info вызывался независимо от статуса результата,
    # что маскировало реальные ошибки транскрибирования в логах.
    if res.status != "ok":
        logger.error(
            "PROD failed | cached=%s | txt=%s | wall=%.2fs | error=%s",
            "yes" if res.cached else "no",
            res.output_txt,
            res.metrics.wall_time_sec,
            res.error or "unknown",
        )
    else:
        logger.info(
            "PROD done | cached=%s | txt=%s | wall=%.2fs | rtf=%s | lang=%s",
            "yes" if res.cached else "no",
            res.output_txt,
            res.metrics.wall_time_sec,
            f"{res.metrics.rtf:.3f}" if res.metrics.rtf is not None else "n/a",
            res.detected_language or "n/a",
        )

    return res
