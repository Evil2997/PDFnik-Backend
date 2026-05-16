from pathlib import Path

from main_app.domain.work_with_pdf.actions.files.audio.process import run_cmd


def get_audio_duration_sec(path: Path) -> float:
    """
    Возвращает длительность аудио в секундах через ffprobe.

    Использует run_cmd() вместо прямого subprocess.run(), чтобы не дублировать
    логику логирования и обработки ненулевого кода возврата.
    CommandFailedError (подкласс RuntimeError) поднимается при ошибке.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = run_cmd(cmd)
    return float(result.stdout.strip())
