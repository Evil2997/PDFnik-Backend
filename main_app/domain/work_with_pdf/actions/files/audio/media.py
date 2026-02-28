import subprocess
from pathlib import Path


def get_audio_duration_sec(path: Path) -> float:
    """
    Возвращает длительность аудио в секундах через ffprobe.
    Требует установленный ffmpeg.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]

    p = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if p.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {p.stderr}")

    return float(p.stdout.strip())
