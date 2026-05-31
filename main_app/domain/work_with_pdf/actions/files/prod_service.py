import contextlib
import hashlib
import logging
from collections.abc import Callable
from pathlib import Path

from main_app.domain.work_with_pdf.actions.files.audio.targets import (
    fetch_playlist_metadata,
    fetch_playlist_video_urls,
)
from main_app.domain.work_with_pdf.actions.files.models import (
    RunMetrics,
    RunResult,
    TranscribeConfig,
    YouTubeMetadata,
)
from main_app.domain.work_with_pdf.actions.files.ports.run_repository import RunRepository
from main_app.domain.work_with_pdf.actions.files.ports.target_preparer import TargetPreparer
from main_app.domain.work_with_pdf.actions.files.ports.transcribe_engine import TranscribeEngine
from main_app.domain.work_with_pdf.actions.files.run_logic import run_once

logger = logging.getLogger(__name__)


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _format_video_section_header(meta: YouTubeMetadata | None, index: int) -> str:
    title = (meta.title if meta else None) or f"Video {index + 1}"
    header = f"=== {title} ==="
    if meta:
        parts: list[str] = []
        if meta.channel:
            parts.append(meta.channel)
        date = meta.upload_date_str
        if date:
            parts.append(date)
        if meta.duration_sec:
            parts.append(meta.duration_str)
        if parts:
            header += "\n" + " · ".join(parts)
    return header


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


def transcribe_playlist(
    *,
    playlist_url: str,
    cfg: TranscribeConfig,
    out_dir: Path,
    repo: RunRepository,
    engine: TranscribeEngine,
    preparer: TargetPreparer,
    on_progress: Callable[[int, int, str, YouTubeMetadata | None], None] | None = None,
    on_cache_summary: Callable[[int, int], None] | None = None,
) -> RunResult:
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    video_urls = fetch_playlist_video_urls(playlist_url)
    playlist_meta = fetch_playlist_metadata(playlist_url)

    sections: list[str] = []
    total_wall = 0.0
    total_duration = 0.0
    cached_streak = 0

    for i, url in enumerate(video_urls):
        video_dir = out_dir / f"video_{i:03d}"
        try:
            prepared = preparer.prepare(url, work_dir=video_dir)
            res = run_once(
                prepared=prepared,
                cfg=cfg,
                out_dir=video_dir,
                repo=repo,
                engine=engine,
                allow_skip=True,
            )
            if res.status != "ok":
                logger.warning(
                    "[playlist] video %d/%d failed: %s", i + 1, len(video_urls), res.error
                )
                continue

            total_wall += res.metrics.wall_time_sec
            if res.metrics.audio_duration_sec:
                total_duration += res.metrics.audio_duration_sec

            text = res.output_txt.read_text(encoding="utf-8").strip()
            header = _format_video_section_header(prepared.youtube_metadata, i)
            sections.append(f"{header}\n\n{text}")

            if res.cached:
                cached_streak += 1
            else:
                if cached_streak > 0 and on_cache_summary:
                    with contextlib.suppress(Exception):
                        on_cache_summary(cached_streak, len(video_urls))
                    cached_streak = 0
                if on_progress:
                    with contextlib.suppress(Exception):
                        on_progress(i + 1, len(video_urls), url, prepared.youtube_metadata)

        except Exception as e:
            logger.warning("[playlist] video %d/%d (%s) error: %s", i + 1, len(video_urls), url, e)

    if cached_streak > 0 and on_cache_summary:
        with contextlib.suppress(Exception):
            on_cache_summary(cached_streak, len(video_urls))

    if not sections:
        raise RuntimeError(f"All {len(video_urls)} videos in playlist failed: {playlist_url}")

    combined_text = "\n\n---\n\n".join(sections)
    combined_txt = out_dir / "playlist_combined.txt"
    combined_txt.write_text(combined_text, encoding="utf-8")

    rtf = (total_wall / total_duration) if total_duration > 0 else None
    metrics = RunMetrics(
        wall_time_sec=total_wall, audio_duration_sec=total_duration or None, rtf=rtf
    )

    logger.info(
        "[playlist] done | videos=%d/%d | wall=%.2fs",
        len(sections),
        len(video_urls),
        total_wall,
    )

    return RunResult(
        run_key=f"playlist_{_hash(playlist_url)}",
        target_id=f"playlist_{_hash(playlist_url)}",
        output_txt=combined_txt,
        metrics=metrics,
        cached=False,
        status="ok",
        youtube_metadata=playlist_meta,
    )
