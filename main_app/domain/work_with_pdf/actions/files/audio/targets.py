import hashlib
import json
import logging
from pathlib import Path

from main_app.domain.work_with_pdf.actions.files.audio.media import get_audio_duration_sec
from main_app.domain.work_with_pdf.actions.files.audio.process import run_cmd
from main_app.domain.work_with_pdf.actions.files.exceptions import TargetPrepareError
from main_app.domain.work_with_pdf.actions.files.models import PreparedTarget, YouTubeMetadata

logger = logging.getLogger(__name__)

# Максимальная длина description в метаданных.
# Полное описание может быть десятки тысяч символов — обрезаем.
_DESCRIPTION_MAX_LEN = 500


# ----------------------------
# Utils
# ----------------------------


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def is_url(target: str) -> bool:
    return target.startswith("http://") or target.startswith("https://")


# ----------------------------
# YouTube metadata
# ----------------------------


def fetch_youtube_metadata(url: str) -> YouTubeMetadata | None:
    """
    Получает метаданные YouTube-видео через yt-dlp --dump-json.

    Не скачивает видео — только JSON с метаданными.
    При любой ошибке возвращает None (некритично для основного pipeline).

    Возвращает YouTubeMetadata или None.
    """
    try:
        result = run_cmd(
            [
                "yt-dlp",
                "--dump-json",
                "--no-playlist",
                "--quiet",
                url,
            ]
        )
        data: dict = json.loads(result.stdout)

        description = data.get("description") or ""
        if len(description) > _DESCRIPTION_MAX_LEN:
            description = description[:_DESCRIPTION_MAX_LEN] + "…"

        return YouTubeMetadata(
            url=url,
            title=data.get("title"),
            channel=data.get("channel") or data.get("uploader"),
            uploader=data.get("uploader"),
            upload_date=data.get("upload_date"),
            duration_sec=data.get("duration"),
            view_count=data.get("view_count"),
            description=description or None,
            thumbnail_url=data.get("thumbnail"),
        )

    except Exception as e:
        # Метаданные — вспомогательная информация.
        # Не прерываем pipeline при ошибке их получения.
        logger.warning("fetch_youtube_metadata failed for %s: %s", url, e)
        return None


# ----------------------------
# Download
# ----------------------------


def download_audio_from_url(url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    template = str(out_dir / "src_%(id)s.%(ext)s")

    run_cmd(
        [
            "yt-dlp",
            "--no-playlist",
            "--restrict-filenames",
            "-f",
            "bestaudio/best",
            "-o",
            template,
            url,
        ]
    )

    candidates = sorted(
        out_dir.glob("src_*.*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not candidates:
        raise TargetPrepareError("yt-dlp finished but no file was saved")

    return candidates[0]


# ----------------------------
# Normalize
# ----------------------------


def normalize_to_wav_16k_mono(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)

    run_cmd(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ]
    )


# ----------------------------
# Public API
# ----------------------------


def prepare_target(target: str, work_dir: Path) -> PreparedTarget:
    logger.info("Prepare target: %s", target)

    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    youtube_metadata: YouTubeMetadata | None = None

    if is_url(target):
        # Сначала получаем метаданные (не скачивает аудио, быстро).
        # Делаем до скачивания: если URL невалидный — узнаём сразу.
        youtube_metadata = fetch_youtube_metadata(target)
        if youtube_metadata:
            logger.info(
                "YouTube metadata | title=%r | channel=%r | duration=%s",
                youtube_metadata.title,
                youtube_metadata.channel,
                youtube_metadata.duration_str,
            )

        raw_path = download_audio_from_url(target, work_dir / "downloads")
        target_id = f"url_{_hash(target)}"
    else:
        raw_path = Path(target).expanduser().resolve()
        if not raw_path.exists():
            raise TargetPrepareError(f"File not found: {target}")
        target_id = f"file_{_hash(str(raw_path))}"

    base_name = raw_path.stem

    wav_path = work_dir / "prepared" / f"{base_name}__{target_id}.wav"

    if not wav_path.exists():
        logger.info("Normalize to wav: %s -> %s", raw_path.name, wav_path.name)
        normalize_to_wav_16k_mono(raw_path, wav_path)
    else:
        logger.info("Prepared wav cached: %s", wav_path.name)

    duration: float | None = None
    try:
        duration = get_audio_duration_sec(wav_path)
    except Exception:
        logger.warning("Could not detect duration for %s", wav_path.name)

    logger.info(
        "Prepared target ready | wav=%s | duration=%ss",
        wav_path.name,
        f"{duration:.2f}" if duration else "unknown",
    )

    return PreparedTarget(
        target=target,
        target_id=target_id,
        base_name=base_name,
        wav_path=wav_path,
        audio_duration_sec=duration,
        youtube_metadata=youtube_metadata,
    )


def ffmpeg_make_sample(src_wav: Path, dst_wav: Path, *, seconds: int) -> None:
    if seconds <= 0:
        raise ValueError(f"seconds must be > 0, got {seconds}")

    dst_wav.parent.mkdir(parents=True, exist_ok=True)

    run_cmd(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src_wav),
            "-t",
            str(seconds),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dst_wav),
        ]
    )
