from __future__ import annotations

import time
from typing import Any, Literal, Optional

from faststream.rabbit.fastapi import RabbitRouter
from pydantic import BaseModel, ConfigDict, Field

from main_app.core.constants import FILES_ROOT, RUNS_DB_PATH, TXT_OUTPUT_DIR
from main_app.core.logger import logger
from main_app.core.settings import settings
from main_app.domain.work_with_pdf.actions.files.audio.target_preparer import AudioTargetPreparer
from main_app.domain.work_with_pdf.actions.files.models import TranscribeConfig
from main_app.domain.work_with_pdf.actions.files.prod_service import transcribe as prod_transcribe
from main_app.domain.work_with_pdf.actions.files.sqlite.sqlite_repo import SqliteRunRepository
from main_app.domain.work_with_pdf.actions.files.whisper_engine import WhisperEngine


class TxtTarget(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["storage_key", "url"]
    value: str


class TxtCfgOverrides(BaseModel):
    model_config = ConfigDict(frozen=True)
    model: Optional[str] = None
    device: Optional[str] = None
    compute_type: Optional[str] = None
    threads: Optional[int] = Field(default=None, ge=1)
    workers: Optional[int] = Field(default=None, ge=1)
    beam_size: Optional[int] = Field(default=None, ge=1)
    patience: Optional[float] = Field(default=None, ge=0.0)
    vad: Optional[bool] = None
    lang: Optional[str] = None


class TxtTranscribeJob(BaseModel):
    job_id: str
    chat_id: int
    reply_to_message_id: Optional[int] = None
    target: TxtTarget
    cfg: Optional[TxtCfgOverrides] = None
    attempt: int = 1
    max_attempts: int = 3


class TxtResult(BaseModel):
    job_id: str
    chat_id: int
    status: Literal["ok", "failed"]
    txt: Optional[dict] = None  # {"storage_key": "..."}
    cached: bool = False
    metrics: dict = Field(default_factory=dict)
    detected_language: Optional[str] = None
    error: Optional[str] = None


def _build_cfg(overrides: Optional[TxtCfgOverrides]) -> TranscribeConfig:
    ov = overrides or TxtCfgOverrides()

    return TranscribeConfig(
        model=ov.model or settings.TRANSCRIBE_MODEL,
        device=ov.device or settings.TRANSCRIBE_DEVICE,
        compute_type=ov.compute_type if ov.compute_type is not None else settings.TRANSCRIBE_COMPUTE_TYPE,
        threads=ov.threads or settings.TRANSCRIBE_THREADS,
        workers=ov.workers or settings.TRANSCRIBE_WORKERS,
        beam_size=ov.beam_size or settings.TRANSCRIBE_BEAM_SIZE,
        patience=ov.patience if ov.patience is not None else settings.TRANSCRIBE_PATIENCE,
        vad=ov.vad if ov.vad is not None else settings.TRANSCRIBE_VAD,
        lang=ov.lang or settings.TRANSCRIBE_LANG,
    )


def _resolve_target(job: TxtTranscribeJob) -> str:
    if job.target.kind == "url":
        return job.target.value

    # storage_key -> abs path
    abs_path = (FILES_ROOT / job.target.value).resolve()
    return str(abs_path)


def register_txt_consumers(router: RabbitRouter) -> None:
    repo = SqliteRunRepository(RUNS_DB_PATH)
    engine = WhisperEngine()  # model из settings
    preparer = AudioTargetPreparer()

    @router.subscriber("txt.transcribe")
    async def handle_txt_transcribe(data: dict[str, Any]):
        started = time.time()

        try:
            job = TxtTranscribeJob.model_validate(data)
        except Exception as e:
            logger.error(f"[TXT] invalid payload: {e}")
            await router.broker.publish(
                message=TxtResult(
                    job_id=data.get("job_id", "unknown"),
                    chat_id=int(data.get("chat_id", 0) or 0),
                    status="failed",
                    error=f"Invalid payload: {e}",
                ).model_dump(),
                queue="txt.send",
            )
            return

        logger.info(f"[TXT] job_id={job.job_id} chat_id={job.chat_id} attempt={job.attempt}/{job.max_attempts}")

        try:
            cfg = _build_cfg(job.cfg)
            target = _resolve_target(job)

            res = prod_transcribe(
                target=target,
                cfg=cfg,
                out_dir=TXT_OUTPUT_DIR,
                repo=repo,
                engine=engine,
                preparer=preparer,
            )

            storage_key = res.output_txt.relative_to(FILES_ROOT).as_posix()
            wall_time = round(time.time() - started, 3)

            await router.broker.publish(
                message=TxtResult(
                    job_id=job.job_id,
                    chat_id=job.chat_id,
                    status="ok",
                    txt={"storage_key": storage_key},
                    cached=res.cached,
                    metrics={"wall_time_sec": wall_time},
                    detected_language=res.detected_language,
                ).model_dump(),
                queue="txt.send",
            )

            logger.info(f"[TXT DONE] job_id={job.job_id} storage_key={storage_key} cached={res.cached}")

        except FileNotFoundError as e:
            await router.broker.publish(
                message=TxtResult(
                    job_id=job.job_id,
                    chat_id=job.chat_id,
                    status="failed",
                    error=f"File not found: {e}",
                ).model_dump(),
                queue="txt.send",
            )
            logger.error(f"[TXT ERROR] file not found: {e}")

        except Exception as e:
            logger.error(f"[TXT ERROR] job_id={job.job_id}: {e}")

            if job.attempt < job.max_attempts:
                next_job = job.model_copy(update={"attempt": job.attempt + 1})
                await router.broker.publish(message=next_job.model_dump(), queue="txt.transcribe")
                logger.info(f"[TXT] requeued job_id={job.job_id} attempt={next_job.attempt}/{next_job.max_attempts}")
            else:
                await router.broker.publish(
                    message=TxtResult(
                        job_id=job.job_id,
                        chat_id=job.chat_id,
                        status="failed",
                        error=str(e),
                    ).model_dump(),
                    queue="txt.send",
                )
