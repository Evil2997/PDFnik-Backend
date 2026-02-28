import hashlib
import logging
from pathlib import Path
from typing import Optional

from main_app.domain.work_with_pdf.actions.files.audio.media import get_audio_duration_sec
from main_app.domain.work_with_pdf.actions.files.audio.process import run_cmd
from main_app.domain.work_with_pdf.actions.files.exceptions import TargetPrepareError
from main_app.domain.work_with_pdf.actions.files.models import PreparedTarget

logger = logging.getLogger(__name__)


# ----------------------------
# Utils
# ----------------------------

def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def is_url(target: str) -> bool:
    return target.startswith("http://") or target.startswith("https://")


# ----------------------------
# Download
# ----------------------------

def download_audio_from_url(url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    template = str(out_dir / "src_%(id)s.%(ext)s")

    run_cmd([
        "yt-dlp",
        "--no-playlist",
        "--restrict-filenames",
        "-f", "bestaudio/best",
        "-o", template,
        url,
    ])

    candidates = sorted(
        out_dir.glob("src_*.*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not candidates:
        raise TargetPrepareError("yt-dlp finished but no file was saved")

    return candidates[0]


# ----------------------------
# Normalize
# ----------------------------

def normalize_to_wav_16k_mono(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)

    run_cmd([
        "ffmpeg",
        "-y",
        "-i", str(src),
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(dst),
    ])


# ----------------------------
# Public API
# ----------------------------

def prepare_target(target: str, work_dir: Path) -> PreparedTarget:
    logger.info("Prepare target: %s", target)

    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    if is_url(target):
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

    duration: Optional[float] = None
    try:
        duration = get_audio_duration_sec(wav_path)
    except Exception:
        logger.warning("Could not detect duration for %s", wav_path.name)

    logger.info(
        "Prepared target ready | wav=%s | duration=%ss",
        wav_path.name,
        f"{duration:.2f}" if duration else "unknown"
    )

    return PreparedTarget(
        target=target,
        target_id=target_id,
        base_name=base_name,
        wav_path=wav_path,
        audio_duration_sec=duration,
    )


def ffmpeg_make_sample(src_wav: Path, dst_wav: Path, *, seconds: int) -> None:
    """
    Создаёт WAV-сэмпл первых N секунд из уже нормализованного WAV.
    Используется в BENCH, чтобы гонять матрицу на коротком фрагменте.

    Важно:
    - ожидается, что src_wav уже whisper-compatible (16k mono pcm_s16le)
    - dst_wav будет таким же форматом
    """
    if seconds <= 0:
        raise ValueError(f"seconds must be > 0, got {seconds}")

    dst_wav.parent.mkdir(parents=True, exist_ok=True)

    run_cmd([
        "ffmpeg",
        "-y",
        "-i", str(src_wav),
        "-t", str(seconds),
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(dst_wav),
    ])
