from pathlib import Path

from main_app.domain.work_with_pdf.actions.files.audio.targets import prepare_target, ffmpeg_make_sample
from main_app.domain.work_with_pdf.actions.files.models import PreparedTarget
from main_app.domain.work_with_pdf.actions.files.ports.target_preparer import TargetPreparer


class AudioTargetPreparer(TargetPreparer):
    def prepare(self, target: str, *, work_dir: Path) -> PreparedTarget:
        return prepare_target(target, work_dir=work_dir)

    def make_sample(self, *, src_wav: Path, dst_wav: Path, seconds: int) -> Path:
        ffmpeg_make_sample(src_wav, dst_wav, seconds=seconds)
        return dst_wav
