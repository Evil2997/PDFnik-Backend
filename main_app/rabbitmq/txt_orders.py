import asyncio
import hashlib
import time
from typing import Any, Literal

from faststream.rabbit.fastapi import RabbitRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator

from main_app.core.constants import FILES_ROOT, RUNS_DB_PATH
from main_app.core.logger import logger
from main_app.core.settings import settings
from main_app.domain.work_with_pdf.actions.files.audio.audio_target_preparer import (
    AudioTargetPreparer,
)
from main_app.domain.work_with_pdf.actions.files.generate_txt_path import generate_txt_path
from main_app.domain.work_with_pdf.actions.files.models import TranscribeConfig, YouTubeMetadata
from main_app.domain.work_with_pdf.actions.files.prod_service import transcribe as prod_transcribe
from main_app.domain.work_with_pdf.actions.files.run_logic import make_run_key, resolve_compute_type
from main_app.domain.work_with_pdf.actions.files.sqlite.sqlite_repo import SqliteRunRepository
from main_app.domain.work_with_pdf.actions.files.whisper_engine import WhisperEngine

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class TxtTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["storage_key", "url"]
    value: str


class TxtReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    chat_id: int
    reply_to_message_id: int | None = None


class TxtDelivery(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_type: str | None = None
    mode: str | None = None


class TxtCfgOverrides(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str | None = None
    device: str | None = None
    compute_type: str | None = None
    threads: int | None = Field(default=None, ge=1)
    workers: int | None = Field(default=None, ge=1)
    beam_size: int | None = Field(default=None, ge=1)
    patience: float | None = Field(default=None, ge=0.0)
    vad: bool | None = None
    lang: str | None = None


class TxtTranscribeJob(BaseModel):
    job_id: str
    target: TxtTarget
    reply: TxtReply | None = None
    delivery: TxtDelivery | None = None
    cfg: TxtCfgOverrides | None = None
    attempt: int = 1
    max_attempts: int = 3

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        payload = dict(data)

        if payload.get("target") is None:
            storage_key = payload.get("storage_key")
            input_url = payload.get("input_url")

            if storage_key:
                payload["target"] = {"kind": "storage_key", "value": storage_key}
            elif input_url:
                payload["target"] = {"kind": "url", "value": input_url}

        if payload.get("reply") is None:
            chat_id = payload.get("chat_id")
            reply_to_message_id = payload.get("reply_to_message_id")

            if chat_id is not None:
                payload["reply"] = {
                    "chat_id": chat_id,
                    "reply_to_message_id": reply_to_message_id,
                }

        if payload.get("delivery") is None:
            source_type = payload.get("source_type")
            mode = payload.get("mode")

            if source_type is not None or mode is not None:
                payload["delivery"] = {"source_type": source_type, "mode": mode}

        return payload


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class TxtDoneResult(BaseModel):
    job_id: str
    status: Literal["ok", "error"]
    txt_storage_key: str | None = None
    reply: TxtReply | None = None
    delivery: TxtDelivery | None = None
    cached: bool | None = None
    error: str | None = None
    # YouTube metadata: заполняется только для source_type="youtube"
    # Telegram-bot использует это для формирования PDF-заголовка.
    youtube_metadata: YouTubeMetadata | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_inflight_lock_guard = asyncio.Lock()
_inflight_locks: dict[str, asyncio.Lock] = {}


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _build_cfg(overrides: TxtCfgOverrides | None) -> TranscribeConfig:
    ov = overrides or TxtCfgOverrides()
    return TranscribeConfig(
        model=ov.model or settings.TRANSCRIBE_MODEL,
        device=ov.device or settings.TRANSCRIBE_DEVICE,
        compute_type=ov.compute_type
        if ov.compute_type is not None
        else settings.TRANSCRIBE_COMPUTE_TYPE,
        threads=ov.threads or settings.TRANSCRIBE_THREADS,
        workers=ov.workers or settings.TRANSCRIBE_WORKERS,
        beam_size=ov.beam_size or settings.TRANSCRIBE_BEAM_SIZE,
        patience=ov.patience if ov.patience is not None else settings.TRANSCRIBE_PATIENCE,
        vad=ov.vad if ov.vad is not None else settings.TRANSCRIBE_VAD,
        lang=ov.lang or settings.TRANSCRIBE_LANG,
    )


def _extract_reply_from_raw(data: dict[str, Any]) -> TxtReply | None:
    reply = data.get("reply")
    if isinstance(reply, dict) and reply.get("chat_id") is not None:
        try:
            return TxtReply.model_validate(reply)
        except Exception:
            return None

    chat_id = data.get("chat_id")
    if chat_id is None:
        return None

    try:
        return TxtReply(
            chat_id=int(chat_id),
            reply_to_message_id=data.get("reply_to_message_id"),
        )
    except Exception:
        return None


def _resolve_storage_path(storage_key: str) -> str:
    files_root = FILES_ROOT.resolve()
    abs_path = (files_root / storage_key).resolve()

    try:
        abs_path.relative_to(files_root)
    except ValueError as e:
        raise ValueError(f"storage_key points outside FILES_ROOT: {storage_key}") from e

    return str(abs_path)


def _resolve_target(job: TxtTranscribeJob) -> str:
    if job.target.kind == "url":
        return job.target.value
    return _resolve_storage_path(job.target.value)


def _target_id_for_job(job: TxtTranscribeJob) -> str:
    if job.target.kind == "url":
        return f"url_{_hash(job.target.value)}"
    abs_path = _resolve_storage_path(job.target.value)
    return f"file_{_hash(abs_path)}"


def _run_key_for_job(job: TxtTranscribeJob, cfg: TranscribeConfig) -> str:
    compute_type = resolve_compute_type(cfg)
    target_id = _target_id_for_job(job)
    return make_run_key(target_id, cfg, compute_type)


def _persist_txt_result(source_txt_path, job_id: str):
    dst_path = generate_txt_path(job_id).resolve()
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    text = source_txt_path.read_text(encoding="utf-8")
    dst_path.write_text(text, encoding="utf-8")
    return dst_path


async def _publish_done(router: RabbitRouter, result: TxtDoneResult) -> None:
    await router.broker.publish(
        message=result.model_dump(exclude_none=True),
        queue="txt.done",
    )


async def _get_or_create_run_lock(run_key: str) -> asyncio.Lock:
    async with _inflight_lock_guard:
        lock = _inflight_locks.get(run_key)
        if lock is None:
            lock = asyncio.Lock()
            _inflight_locks[run_key] = lock
        return lock


async def _release_run_lock_if_unused(run_key: str, lock: asyncio.Lock) -> None:
    async with _inflight_lock_guard:
        current = _inflight_locks.get(run_key)
        if current is lock and not lock.locked():
            _inflight_locks.pop(run_key, None)


# ---------------------------------------------------------------------------
# Consumer registration
# ---------------------------------------------------------------------------


def register_txt_consumers(router: RabbitRouter) -> None:
    repo = SqliteRunRepository(RUNS_DB_PATH)
    engine = WhisperEngine()
    preparer = AudioTargetPreparer()

    @router.subscriber("txt.transcribe")
    async def handle_txt_transcribe(data: dict[str, Any]):
        started = time.time()

        try:
            job = TxtTranscribeJob.model_validate(data)
        except Exception as e:
            logger.error("[TXT] invalid payload: %s", e)
            await _publish_done(
                router,
                TxtDoneResult(
                    job_id=str(data.get("job_id", "unknown")),
                    status="error",
                    error=f"Invalid payload: {e}",
                    reply=_extract_reply_from_raw(data),
                ),
            )
            return

        cfg = _build_cfg(job.cfg)
        run_key = _run_key_for_job(job, cfg)

        logger.info(
            "[TXT] received | job_id=%s | target.kind=%s | target.value=%s | run_key=%s | attempt=%s/%s",
            job.job_id,
            job.target.kind,
            job.target.value,
            run_key,
            job.attempt,
            job.max_attempts,
        )

        lock = await _get_or_create_run_lock(run_key)

        if lock.locked():
            logger.info("[TXT] wait in-flight run | job_id=%s | run_key=%s", job.job_id, run_key)

        try:
            async with lock:
                target = _resolve_target(job)
                loop = asyncio.get_running_loop()

                res = await loop.run_in_executor(
                    None,
                    lambda: prod_transcribe(
                        target=target,
                        cfg=cfg,
                        out_dir=generate_txt_path(job.job_id).parent,
                        repo=repo,
                        engine=engine,
                        preparer=preparer,
                    ),
                )

                if res.status != "ok":
                    raise RuntimeError(
                        res.error or f"Transcription failed with status={res.status}"
                    )

                final_txt_path = _persist_txt_result(res.output_txt, job.job_id)
                txt_storage_key = final_txt_path.relative_to(FILES_ROOT.resolve()).as_posix()
                wall_time = round(time.time() - started, 3)

                await _publish_done(
                    router,
                    TxtDoneResult(
                        job_id=job.job_id,
                        status="ok",
                        txt_storage_key=txt_storage_key,
                        reply=job.reply,
                        delivery=job.delivery,
                        cached=res.cached,
                        youtube_metadata=res.youtube_metadata,  # ← прокидываем
                    ),
                )

                logger.info(
                    "[TXT DONE] job_id=%s | run_key=%s | txt_storage_key=%s | cached=%s | "
                    "youtube=%s | wall=%.3fs",
                    job.job_id,
                    run_key,
                    txt_storage_key,
                    res.cached,
                    bool(res.youtube_metadata),
                    wall_time,
                )

        except Exception as e:
            logger.error(
                "[TXT ERROR] job_id=%s | run_key=%s | target.kind=%s | target.value=%s | error=%s",
                job.job_id,
                run_key,
                job.target.kind,
                job.target.value,
                e,
            )

            if job.attempt < job.max_attempts:
                next_job = job.model_copy(update={"attempt": job.attempt + 1})
                await router.broker.publish(
                    message=next_job.model_dump(exclude_none=True),
                    queue="txt.transcribe",
                )
                logger.info(
                    "[TXT] requeued | job_id=%s | run_key=%s | next_attempt=%s/%s",
                    job.job_id,
                    run_key,
                    next_job.attempt,
                    next_job.max_attempts,
                )
                return

            await _publish_done(
                router,
                TxtDoneResult(
                    job_id=job.job_id,
                    status="error",
                    error=str(e),
                    reply=job.reply,
                ),
            )
        finally:
            await _release_run_lock_if_unused(run_key, lock)
