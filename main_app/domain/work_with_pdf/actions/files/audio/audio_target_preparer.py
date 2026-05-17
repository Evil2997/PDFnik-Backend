"""
A concrete implementation of TargetPreparer for audio files.

Renamed from `target_preparer.py` to `audio_target_preparer.py` to
resolve a naming conflict with the port/protocol in `ports/target_preparer.py`.

Update the import in `txt_orders.py`:
from main_app.domain.work_with_pdf.actions.files.audio.audio_target_preparer import AudioTargetPreparer
"""

from pathlib import Path

from main_app.domain.work_with_pdf.actions.files.audio.targets import (
    ffmpeg_make_sample,
    prepare_target,
)
from main_app.domain.work_with_pdf.actions.files.models import PreparedTarget
from main_app.domain.work_with_pdf.actions.files.ports.target_preparer import TargetPreparer


class AudioTargetPreparer(TargetPreparer):
    def prepare(self, target: str, *, work_dir: Path) -> PreparedTarget:
        return prepare_target(target, work_dir=work_dir)

    def make_sample(self, *, src_wav: Path, dst_wav: Path, seconds: int) -> Path:
        ffmpeg_make_sample(src_wav, dst_wav, seconds=seconds)
        return dst_wav
