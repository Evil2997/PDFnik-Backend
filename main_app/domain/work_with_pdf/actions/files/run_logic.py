import hashlib
import logging
import time
from pathlib import Path

from main_app.domain.work_with_pdf.actions.files.exceptions import TranscribeError
from main_app.domain.work_with_pdf.actions.files.models import TranscribeConfig, PreparedTarget, RunResult, RunMetrics
from main_app.domain.work_with_pdf.actions.files.ports.run_repository import RunRepository
from main_app.domain.work_with_pdf.actions.files.ports.transcribe_engine import TranscribeEngine

logger = logging.getLogger(__name__)


def resolve_compute_type(cfg: TranscribeConfig) -> str:
    if cfg.compute_type:
        return cfg.compute_type
    if cfg.device.lower() == "cuda":
        return "float16"
    return "int8"


def make_run_key(target_id: str, cfg: TranscribeConfig, compute_type: str) -> str:
    parts = [
        target_id,
        cfg.model,
        cfg.device,
        compute_type,
        f"thr={cfg.threads}",
        f"wrk={cfg.workers}",
        f"beam={cfg.beam_size}",
        f"pat={cfg.patience}",
        f"vad={int(cfg.vad)}",
        f"lang={cfg.lang}",
    ]
    return "|".join(map(str, parts))


def _stable_id_from_run_key(run_key: str, n: int = 10) -> str:
    return hashlib.sha1(run_key.encode("utf-8")).hexdigest()[:n]


def txt_name_for_run(base_name: str, run_key: str) -> str:
    rid = _stable_id_from_run_key(run_key, n=10)
    return f"{base_name}__{rid}.txt"


def run_once(
        *,
        prepared: PreparedTarget,
        cfg: TranscribeConfig,
        out_dir: Path,
        repo: RunRepository,
        engine: TranscribeEngine,
        allow_skip: bool,
) -> RunResult:
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    compute = resolve_compute_type(cfg)
    run_key = make_run_key(prepared.target_id, cfg, compute)

    out_txt = out_dir / txt_name_for_run(prepared.base_name, run_key)

    if allow_skip and out_txt.exists():
        row = repo.get(run_key)
        if row:
            metrics = RunMetrics(
                wall_time_sec=0.0,
                audio_duration_sec=prepared.audio_duration_sec,
                rtf=None,
            )
            return RunResult(
                run_key=run_key,
                target_id=prepared.target_id,
                output_txt=Path(row.get("output_txt") or out_txt),
                detected_language=None,
                metrics=metrics,
                cached=True,
                status=row.get("status") or "ok",
                error=None,
            )

    logger.info("Transcribe | txt=%s", out_txt.name)

    t0 = time.perf_counter()
    try:
        text, detected = engine.transcribe(prepared.wav_path, cfg)
        wall = time.perf_counter() - t0

        out_txt.write_text(text, encoding="utf-8")

        audio_dur = prepared.audio_duration_sec
        rtf = (wall / audio_dur) if (audio_dur and audio_dur > 0) else None

        metrics = RunMetrics(wall_time_sec=wall, audio_duration_sec=audio_dur, rtf=rtf)

        # MINIMAL upsert
        repo.upsert(
            {
                "run_key": run_key,
                "status": "ok",
                "output_txt": str(out_txt),
            }
        )

        return RunResult(
            run_key=run_key,
            target_id=prepared.target_id,
            output_txt=out_txt,
            detected_language=detected,
            metrics=metrics,
            cached=False,
            status="ok",
            error=None,
        )

    except Exception as e:
        err = e if isinstance(e, TranscribeError) else TranscribeError(str(e))

        wall = time.perf_counter() - t0
        audio_dur = prepared.audio_duration_sec
        rtf = (wall / audio_dur) if (audio_dur and audio_dur > 0) else None
        metrics = RunMetrics(wall_time_sec=wall, audio_duration_sec=audio_dur, rtf=rtf)

        repo.upsert(
            {
                "run_key": run_key,
                "status": "failed",
                "output_txt": str(out_txt),
            }
        )

        return RunResult(
            run_key=run_key,
            target_id=prepared.target_id,
            output_txt=out_txt,
            detected_language=None,
            metrics=metrics,
            cached=False,
            status="failed",
            error=str(err),
        )
