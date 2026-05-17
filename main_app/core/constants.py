# /home/dmitriy/PycharmProjects/FastAPI-Learning/main_app/core/constants.py
# repo: PDFnik-Backend

import pathlib
from typing import Final

from main_app.core.settings import settings

RABBITMQ_URL: Final[str] = settings.RABBITMQ_URL

# Пути к файловому хранилищу.
# В docker-compose смонтированы как volume files_storage.
# mkdir вынесен в main.py — не должен выполняться при импорте модуля,
# иначе тесты падают с PermissionError на /data_files_storage.
FILES_ROOT: Final[pathlib.Path] = pathlib.Path("/data_files_storage")
PDF_OUTPUT_DIR: Final[pathlib.Path] = FILES_ROOT / "pdfs"
TXT_OUTPUT_DIR: Final[pathlib.Path] = FILES_ROOT / "txts"
RUNS_DB_PATH: Final[pathlib.Path] = FILES_ROOT / "runs.db"

FONT_TYPE: Final[str] = "DejaVuSans"
FONT_PATH: Final[str] = "/app/fonts/DejaVuSans.ttf"
