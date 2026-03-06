import pathlib

from main_app.core.constants import TXT_OUTPUT_DIR


def generate_txt_path(job_id: str) -> pathlib.Path:
    safe_job_id = "".join(
        ch if ch.isalnum() or ch in {"-", "_"} else "_"
        for ch in job_id
    ).strip("_")

    if not safe_job_id:
        safe_job_id = "job"

    return TXT_OUTPUT_DIR / f"{safe_job_id}.txt"