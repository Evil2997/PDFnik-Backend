import logging
import subprocess
from typing import Sequence

from main_app.domain.work_with_pdf.actions.files.exceptions import CommandFailedError

logger = logging.getLogger(__name__)


def run_cmd(cmd: Sequence[str], *, capture_output: bool = True, text: bool = True) -> subprocess.CompletedProcess:
    cmd_list = list(cmd)
    logger.debug("Run cmd: %s", " ".join(cmd_list))

    p = subprocess.run(
        cmd_list,
        capture_output=capture_output,
        text=text,
        check=False,
    )

    if p.returncode != 0:
        stderr = p.stderr or ""
        logger.error("Cmd failed (%s): %s", p.returncode, " ".join(cmd_list))
        if stderr.strip():
            logger.error("stderr: %s", stderr.strip())
        raise CommandFailedError(cmd_list, p.returncode, stderr)

    return p
