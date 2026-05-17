# /home/dmitriy/PycharmProjects/FastAPI-Learning/main_app/core/constants.py
# repo: PDFnik-Backend

import pathlib
from typing import Final

from main_app.core.settings import settings

RABBITMQ_URL: Final[str] = settings.RABBITMQ_URL

# Root of the file storage.
# Mounted as a Docker volume (files_storage) in docker-compose.
# mkdir is called in main.py at startup — not here, to avoid
# PermissionError when importing in test environments.
FILES_ROOT: Final[pathlib.Path] = pathlib.Path("/data_files_storage")
PDF_OUTPUT_DIR: Final[pathlib.Path] = FILES_ROOT / "pdfs"
TXT_OUTPUT_DIR: Final[pathlib.Path] = FILES_ROOT / "txts"
RUNS_DB_PATH: Final[pathlib.Path] = FILES_ROOT / "runs.db"
