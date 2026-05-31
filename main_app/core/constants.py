# /home/dmitriy/PycharmProjects/PDFnik-Backend/main_app/core/constants.py
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

# Font is installed from fonts-dejavu-core in the Docker image.
# Path is computed relative to this file: main_app/core/ → parents[2] = /app.
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
_FONT_TYPE = "DejaVuSans"
_FONT_PATH = str(_PROJECT_ROOT / "fonts" / "DejaVuSans.ttf")
