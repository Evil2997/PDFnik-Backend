import hashlib
import json
import logging
from pathlib import Path

from main_app.domain.work_with_pdf.actions.files.audio.media import get_audio_duration_sec
from main_app.domain.work_with_pdf.actions.files.audio.process import run_cmd
from main_app.domain.work_with_pdf.actions.files.exceptions import TargetPrepareError
from main_app.domain.work_with_pdf.actions.files.models import PreparedTarget, YouTubeMetadata

logger = logging.getLogger(__name__)

# Maximum length of the description field in metadata.
# Full descriptions can be tens of thousands of characters — truncate.
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
    Fetches YouTube video metadata via yt-dlp --dump-json.

    Does not download video — only JSON metadata.
    Returns None on any error (non-critical for the main pipeline).
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
        # Metadata is supplementary — do not interrupt the pipeline on failure.
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
        # Fetch metadata first (no audio download, fast).
        # Done before downloading: invalid URLs fail early.
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


# ----------------------------
# Playlist support
# ----------------------------


def is_playlist_url(url: str) -> bool:
    """Returns True for youtube.com/playlist?list=... URLs."""
    return "youtube.com/playlist" in url.lower()


def fetch_playlist_video_urls(playlist_url: str) -> list[str]:
    """Returns all video URLs from a YouTube playlist via yt-dlp --flat-playlist."""
    result = run_cmd(
        [
            "yt-dlp",
            "--flat-playlist",
            "--print",
            "%(webpage_url)s",
            "--quiet",
            playlist_url,
        ]
    )
    urls = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not urls:
        raise TargetPrepareError(f"No videos found in playlist: {playlist_url}")
    logger.info("Playlist has %d videos: %s", len(urls), playlist_url)
    return urls


def fetch_playlist_metadata(playlist_url: str) -> YouTubeMetadata | None:
    """Fetches playlist-level metadata (title, channel) without downloading videos."""
    try:
        result = run_cmd(
            [
                "yt-dlp",
                "--flat-playlist",
                "-J",
                "--quiet",
                playlist_url,
            ]
        )
        data: dict = json.loads(result.stdout)
        return YouTubeMetadata(
            url=playlist_url,
            title=data.get("title"),
            channel=data.get("channel") or data.get("uploader"),
            uploader=data.get("uploader"),
        )
    except Exception as e:
        logger.warning("fetch_playlist_metadata failed for %s: %s", playlist_url, e)
        return None


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
